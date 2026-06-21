"""
Scraper for Infocasas Peru rental listings.

Extracts structured JSON directly from __NEXT_DATA__ embedded in each
search results page — no JS rendering needed. Data is complete and clean.

Districts covered: Miraflores, San Isidro, Surco, Magdalena del Mar.
"""

import json
import logging
import re
import time
from datetime import date, datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from scraping.utils import get_session, rate_limit, init_db, save_listing, already_scraped

logger = logging.getLogger(__name__)

BASE_URL = "https://www.infocasas.com.pe"

# Internal name → Infocasas URL slug
DISTRITOS: dict[str, str] = {
    "miraflores": "lima-miraflores",
    "san-isidro": "lima-san-isidro",
    "surco":      "lima-surco",
    "magdalena":  "lima-magdalena-del-mar",
}

SEARCH_PATH = "/alquiler/departamentos/{slug}?page={page}"

# Amenities worth tracking as binary features for the model
AMENITY_KEYWORDS = {
    "piscina":    ["piscina", "pool"],
    "gimnasio":   ["gimnasio", "gym"],
    "cochera":    ["cochera", "estacionamiento", "garaje"],
    "ascensor":   ["ascensor", "elevador"],
    "seguridad":  ["seguridad", "vigilancia", "conserje"],
    "terraza":    ["terraza", "roof"],
    "amoblado":   ["amoblado", "amueblado", "furnished"],
    "aire":       ["aire acondicionado", "a/c", "ac"],
}


# ---------------------------------------------------------------------------
# Page-level scraping
# ---------------------------------------------------------------------------

def get_listings_from_page(session: requests.Session, slug: str, page: int) -> tuple[list[dict], dict]:
    """
    Fetch one search results page.
    Returns (raw_listings_list, paginatorInfo).
    """
    url = BASE_URL + SEARCH_PATH.format(slug=slug, page=page)
    try:
        resp = session.get(url, timeout=20)
    except requests.RequestException as e:
        logger.warning(f"Request failed {url}: {e}")
        return [], {}

    if resp.status_code != 200:
        logger.warning(f"HTTP {resp.status_code} {url}")
        return [], {}

    soup = BeautifulSoup(resp.text, "lxml")
    next_data_tag = soup.find("script", id="__NEXT_DATA__")
    if not next_data_tag:
        logger.warning(f"No __NEXT_DATA__ at {url}")
        return [], {}

    try:
        data = json.loads(next_data_tag.string)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error at {url}: {e}")
        return [], {}

    search_fast = (
        data.get("props", {})
        .get("pageProps", {})
        .get("fetchResult", {})
        .get("searchFast", {})
    )
    listings = search_fast.get("data", [])
    paginator = search_fast.get("paginatorInfo", {})
    return listings, paginator


# ---------------------------------------------------------------------------
# Listing normalization
# ---------------------------------------------------------------------------

def normalize_listing(raw: dict, district_name: str) -> Optional[dict]:
    """Convert raw Infocasas JSON object to our DB schema dict."""
    listing_id = str(raw.get("id", ""))
    link = raw.get("link", "")
    url = BASE_URL + link if link.startswith("/") else link

    # Price
    price_obj = raw.get("price") or {}
    currency_name = (price_obj.get("currency") or {}).get("name", "")
    price_amount = price_obj.get("amount")
    price_usd = raw.get("price_amount_usd")

    if currency_name == "S/":
        price_pen = price_amount
    elif currency_name in ("US$", "USD", "$") and price_usd:
        price_pen = None
    else:
        price_pen = None

    if not (price_pen or price_usd):
        return None  # skip listings without any price

    # Area: prefer m2apto (net apt area), fallback to m2 or m2Built
    area = raw.get("m2apto") or raw.get("m2") or raw.get("m2Built")

    # Days on market (proxy: today - created_at)
    days_listed: Optional[int] = None
    created_str = raw.get("created_at")
    if created_str:
        try:
            created = date.fromisoformat(str(created_str)[:10])
            days_listed = (date.today() - created).days
        except ValueError:
            pass

    # Amenities: extract binary flags from facilities list
    facilities = raw.get("facilities") or []
    facility_names = " ".join(f.get("name", "").lower() for f in facilities)
    desc_text = re.sub(r"<[^>]+>", " ", raw.get("description") or "").lower()
    combined_text = facility_names + " " + desc_text

    amenities: dict[str, int] = {}
    for key, keywords in AMENITY_KEYWORDS.items():
        amenities[key] = int(any(kw in combined_text for kw in keywords))

    # Has garage: also check dedicated field
    if raw.get("garage", 0):
        amenities["cochera"] = 1

    # District: use passed-in name (from URL slug) as authoritative source
    district = district_name

    # Raw description (stripped of HTML) for Claude parser
    description_clean = re.sub(r"<[^>]+>", " ", raw.get("description") or "").strip()
    description_clean = re.sub(r"\s+", " ", description_clean)[:4000]

    return {
        "listing_id":      listing_id,
        "url":             url,
        "district":        district,
        "title":           (raw.get("title") or "")[:500],
        "price_pen":       price_pen,
        "price_usd":       price_usd,
        "price_raw":       price_amount,
        "currency":        "PEN" if currency_name == "S/" else "USD",
        "area_m2":         float(area) if area else None,
        "bedrooms":        raw.get("bedrooms"),
        "bathrooms":       raw.get("bathrooms"),
        "floor":           raw.get("floor"),
        "antiquity_years": raw.get("antiquity"),
        "address":         (raw.get("address") or "")[:300],
        "description":     description_clean,
        "amenities_raw":   json.dumps(amenities),
        "days_listed":     days_listed,
        "scraped_at":      datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_scraper(
    db_path: str = "data/raw/listings.db",
    max_per_distrito: int = 200,
    max_pages: int = 30,
) -> int:
    """Scrape all target districts. Returns total new listings saved."""
    conn = init_db(db_path)
    session = get_session()
    total_new = 0

    for nombre, slug in DISTRITOS.items():
        logger.info(f"── {nombre} ({slug}) ──")
        distrito_new = 0

        for page in range(1, max_pages + 1):
            if distrito_new >= max_per_distrito:
                break

            rate_limit(min_delay=1.5, jitter=1.0)
            raw_listings, paginator = get_listings_from_page(session, slug, page)

            if not raw_listings:
                logger.info(f"  page {page}: empty — stopping {nombre}")
                break

            logger.info(
                f"  page {page}/{paginator.get('lastPage','?')}: "
                f"{len(raw_listings)} raw listings"
            )

            for raw in raw_listings:
                if distrito_new >= max_per_distrito:
                    break

                listing_url = BASE_URL + raw.get("link", "")
                if already_scraped(conn, listing_url):
                    continue

                normalized = normalize_listing(raw, nombre)
                if normalized and save_listing(conn, normalized):
                    distrito_new += 1
                    total_new += 1

            if not paginator.get("hasMorePages", False):
                logger.info(f"  last page reached for {nombre}")
                break

        logger.info(f"  {nombre}: {distrito_new} new listings saved")

    conn.close()
    logger.info(f"Total new: {total_new}")
    return total_new
