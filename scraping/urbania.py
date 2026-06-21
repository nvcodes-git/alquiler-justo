"""
Scraper for Urbania.pe rental listings.

Targets: Miraflores, San Isidro, Surco, Magdalena del Mar.
Strategy: search pagination → listing URLs → detail page extraction.
Extraction order: __NEXT_DATA__ JSON → JSON-LD → CSS/regex fallback.
"""

import re
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from scraping.utils import get_session, rate_limit, init_db, save_listing, already_scraped

logger = logging.getLogger(__name__)

BASE_URL = "https://urbania.pe"

# Map internal name → Urbania slug used in search URLs
DISTRITOS: dict[str, str] = {
    "miraflores":  "miraflores-lima",
    "san-isidro":  "san-isidro-lima",
    "surco":       "santiago-de-surco-lima",
    "magdalena":   "magdalena-del-mar-lima",
}

# Tried in order; first match wins
SEARCH_URL_PATTERNS = [
    "{base}/buscar/alquiler-de-departamentos-en-{distrito}?page={page}",
    "{base}/buscar/alquiler-de-departamentos-en-{distrito}&page={page}",
]


# ---------------------------------------------------------------------------
# Search page
# ---------------------------------------------------------------------------

def get_listing_urls_from_search(session: requests.Session, distrito_slug: str, page: int) -> list[str]:
    """Fetch one search results page and return deduplicated listing URLs."""
    for pattern in SEARCH_URL_PATTERNS:
        url = pattern.format(base=BASE_URL, distrito=distrito_slug, page=page)
        try:
            resp = session.get(url, timeout=20)
        except requests.RequestException as e:
            logger.warning(f"Request failed for {url}: {e}")
            return []

        if resp.status_code == 404:
            continue
        if resp.status_code != 200:
            logger.warning(f"HTTP {resp.status_code} for {url}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        urls = _extract_listing_urls(soup, resp.text)
        if urls:
            return urls

    return []


def _extract_listing_urls(soup: BeautifulSoup, raw_html: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []

    # Strategy 1: anchor tags with /inmueble/ in href
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        if "/inmueble/" in href:
            full = href if href.startswith("http") else BASE_URL + href
            full = full.split("?")[0]  # drop query params
            if full not in seen:
                seen.add(full)
                urls.append(full)

    # Strategy 2: regex over raw HTML (catches URLs in JS bundles)
    if not urls:
        for match in re.finditer(r'["\'](/inmueble/[^"\'?\s]+)', raw_html):
            path = match.group(1).split("?")[0]
            full = BASE_URL + path
            if full not in seen:
                seen.add(full)
                urls.append(full)

    return urls


# ---------------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------------

def scrape_listing(session: requests.Session, url: str) -> Optional[dict]:
    try:
        resp = session.get(url, timeout=20)
    except requests.RequestException as e:
        logger.warning(f"Request failed for {url}: {e}")
        return None

    if resp.status_code != 200:
        logger.warning(f"HTTP {resp.status_code} for {url}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    listing: dict = {
        "url": url,
        "listing_id": _id_from_url(url),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }

    # Extraction pipeline — each enriches `listing` in place
    _try_next_data(resp.text, listing)
    _try_jsonld(soup, listing)
    if not _has_price(listing):
        _try_css_regex(soup, listing)

    # Always grab description from visible text if not found yet
    if not listing.get("description"):
        listing["description"] = _visible_text(soup)[:4000]

    return listing if _has_price(listing) else None


# ---------------------------------------------------------------------------
# Extraction strategies
# ---------------------------------------------------------------------------

def _try_next_data(html: str, listing: dict) -> None:
    """Parse Next.js __NEXT_DATA__ embedded JSON."""
    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return

    flat = json.dumps(data)  # search flat string for field patterns

    _regex_fields(flat, listing)
    _deep_search(data, listing)


def _try_jsonld(soup: BeautifulSoup, listing: dict) -> None:
    """Parse JSON-LD structured data blocks."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, AttributeError):
            continue
        if isinstance(data, list):
            data = data[0] if data else {}

        _type = data.get("@type", "")
        if _type not in ("Apartment", "House", "RealEstateListing", "Product", "Offer"):
            continue

        offers = data.get("offers", {})
        price = offers.get("price") or data.get("price")
        currency = offers.get("priceCurrency") or data.get("priceCurrency", "PEN")
        if price and not _has_price(listing):
            try:
                p = float(str(price).replace(",", "").replace(" ", ""))
            except ValueError:
                p = None
            if p:
                listing["price_raw"] = p
                listing["currency"] = currency
                if currency == "PEN":
                    listing["price_pen"] = p
                elif currency == "USD":
                    listing["price_usd"] = p

        if not listing.get("description"):
            listing["description"] = data.get("description", "")
        if not listing.get("address"):
            addr = data.get("address")
            listing["address"] = str(addr) if addr else ""


def _try_css_regex(soup: BeautifulSoup, listing: dict) -> None:
    """Last-resort: regex patterns over visible text."""
    text = _visible_text(soup)

    pen = re.search(r"S[/\.\s]+\s*([\d,]+)", text)
    usd = re.search(r"(?:USD|US\$|\$)\s*([\d,]+)", text)
    if pen:
        listing["price_pen"] = float(pen.group(1).replace(",", ""))
        listing["currency"] = "PEN"
    elif usd:
        listing["price_usd"] = float(usd.group(1).replace(",", ""))
        listing["currency"] = "USD"

    if not listing.get("area_m2"):
        m = re.search(r"(\d+(?:\.\d+)?)\s*m[²2]", text, re.IGNORECASE)
        if m:
            listing["area_m2"] = float(m.group(1))

    if not listing.get("bedrooms"):
        m = re.search(r"(\d+)\s*(?:dormitorio|habitaci[oó]n|cuarto|dorm\.?)\b", text, re.IGNORECASE)
        if m:
            listing["bedrooms"] = int(m.group(1))

    if not listing.get("bathrooms"):
        m = re.search(r"(\d+)\s*(?:ba[ñn]o|ss\.?\s*hh\.?)\b", text, re.IGNORECASE)
        if m:
            listing["bathrooms"] = int(m.group(1))


# ---------------------------------------------------------------------------
# Helpers for __NEXT_DATA__ parsing
# ---------------------------------------------------------------------------

_FIELD_PATTERNS: list[tuple[str, str, str]] = [
    # (regex pattern, capture group type, listing key)
    (r'"(?:price|totalPrice|rentPrice)"\s*:\s*"?([\d\.]+)"?', "float", "price_raw"),
    (r'"pricePen"\s*:\s*"?([\d\.]+)"?',                       "float", "price_pen"),
    (r'"priceUsd"\s*:\s*"?([\d\.]+)"?',                       "float", "price_usd"),
    (r'"currency"\s*:\s*"([A-Z]{3})"',                        "str",   "currency"),
    (r'"(?:area|totalArea|builtArea)"\s*:\s*"?([\d\.]+)"?',   "float", "area_m2"),
    (r'"(?:bedrooms?Count|bedrooms|rooms|dormitorios)"\s*:\s*"?(\d+)"?', "int", "bedrooms"),
    (r'"(?:bathrooms?Count|bathrooms|banos)"\s*:\s*"?(\d+)"?', "int",  "bathrooms"),
    (r'"(?:floor|piso)"\s*:\s*"?(\d+)"?',                     "int",   "floor"),
    (r'"(?:antiquity|antiquityYears|yearBuilt)"\s*:\s*"?(\d+)"?', "int", "antiquity_years"),
    (r'"(?:district|distrito)"\s*:\s*"([^"]{3,50})"',         "str",   "district"),
    (r'"title"\s*:\s*"([^"]{10,200})"',                       "str",   "title"),
    (r'"(?:daysOnMarket|daysListed|diasPublicado)"\s*:\s*"?(\d+)"?', "int", "days_listed"),
]

_CASTERS = {"float": float, "int": int, "str": str}


def _regex_fields(flat: str, listing: dict) -> None:
    for pattern, cast_name, key in _FIELD_PATTERNS:
        if key in listing:
            continue
        m = re.search(pattern, flat, re.IGNORECASE)
        if m:
            try:
                listing[key] = _CASTERS[cast_name](m.group(1).replace(",", ""))
            except (ValueError, KeyError):
                pass

    # Descriptions — take the longest match
    descs = re.findall(
        r'"(?:description|body|observaciones|details?)"\s*:\s*"([^"]{60,})"',
        flat, re.IGNORECASE,
    )
    if descs and not listing.get("description"):
        listing["description"] = max(descs, key=len)


def _deep_search(obj, listing: dict, depth: int = 0) -> None:
    """Recursively walk the parsed JSON object looking for canonical keys."""
    if depth > 8:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = k.lower()
            if kl in ("price", "rentprice", "totalprice") and not _has_price(listing):
                try:
                    p = float(str(v).replace(",", ""))
                    listing["price_raw"] = p
                except (ValueError, TypeError):
                    pass
            elif kl == "pricepen" and not listing.get("price_pen"):
                try:
                    listing["price_pen"] = float(str(v).replace(",", ""))
                except (ValueError, TypeError):
                    pass
            elif kl == "priceusd" and not listing.get("price_usd"):
                try:
                    listing["price_usd"] = float(str(v).replace(",", ""))
                except (ValueError, TypeError):
                    pass
            elif kl in ("area", "totalarea", "builtarea") and not listing.get("area_m2"):
                try:
                    listing["area_m2"] = float(str(v).replace(",", ""))
                except (ValueError, TypeError):
                    pass
            elif kl in ("bedrooms", "bedroomscount", "dormitorios") and not listing.get("bedrooms"):
                try:
                    listing["bedrooms"] = int(v)
                except (ValueError, TypeError):
                    pass
            elif kl in ("bathrooms", "bathroomscount", "banos") and not listing.get("bathrooms"):
                try:
                    listing["bathrooms"] = int(v)
                except (ValueError, TypeError):
                    pass
            elif kl == "district" and not listing.get("district"):
                if isinstance(v, str) and len(v) > 2:
                    listing["district"] = v
            elif kl in ("description", "body", "observaciones") and not listing.get("description"):
                if isinstance(v, str) and len(v) > 50:
                    listing["description"] = v
            _deep_search(v, listing, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _deep_search(item, listing, depth + 1)


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

def _id_from_url(url: str) -> str:
    parts = url.rstrip("/").split("/")
    return parts[-1] or parts[-2]


def _has_price(listing: dict) -> bool:
    return bool(listing.get("price_pen") or listing.get("price_usd") or listing.get("price_raw"))


def _visible_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "meta", "head"]):
        tag.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())


# ---------------------------------------------------------------------------
# Main scraping loop
# ---------------------------------------------------------------------------

def run_scraper(
    db_path: str = "data/raw/listings.db",
    max_per_distrito: int = 200,
    max_pages: int = 15,
) -> int:
    """Scrape all target distritos. Returns total new listings inserted."""
    conn = init_db(db_path)
    session = get_session()
    total_new = 0

    for nombre, slug in DISTRITOS.items():
        logger.info(f"── {nombre} ──")
        distrito_new = 0

        for page in range(1, max_pages + 1):
            if distrito_new >= max_per_distrito:
                break

            rate_limit()
            urls = get_listing_urls_from_search(session, slug, page)

            if not urls:
                logger.info(f"  page {page}: no URLs found — stopping {nombre}")
                break

            new_urls = [u for u in urls if not already_scraped(conn, u)]
            logger.info(f"  page {page}: {len(urls)} URLs, {len(new_urls)} new")

            if not new_urls:
                logger.info(f"  page {page}: all already scraped — stopping {nombre}")
                break

            for url in new_urls:
                if distrito_new >= max_per_distrito:
                    break
                rate_limit()
                listing = scrape_listing(session, url)
                if listing:
                    listing.setdefault("district", nombre)
                    if save_listing(conn, listing):
                        distrito_new += 1
                        total_new += 1
                        logger.debug(f"    saved [{distrito_new}] {url}")
                else:
                    logger.debug(f"    skip (no price) {url}")

        logger.info(f"  {nombre}: {distrito_new} new listings")

    conn.close()
    logger.info(f"Total new listings: {total_new}")
    return total_new
