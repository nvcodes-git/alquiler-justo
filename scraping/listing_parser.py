"""
Fetch and parse a single listing URL from Infocasas.pe.
Returns the same dict schema used by normalize_listing().
No Claude needed — data comes from __NEXT_DATA__ JSON.
"""

import json
import logging
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

from scraping.utils import get_session
from scraping.infocasas import normalize_listing, AMENITY_KEYWORDS, BASE_URL

logger = logging.getLogger(__name__)

KNOWN_DISTRICTS = {
    "miraflores": "miraflores",
    "san isidro": "san-isidro",
    "san-isidro": "san-isidro",
    "surco": "surco",
    "santiago de surco": "surco",
    "magdalena": "magdalena",
    "magdalena del mar": "magdalena",
}


def parse_listing_url(url: str, session: Optional[requests.Session] = None) -> Optional[dict]:
    """
    Fetch a single Infocasas listing URL and return a normalized dict.
    Returns None if URL is unsupported or data can't be extracted.
    """
    if "infocasas.com.pe" not in url:
        return _parse_generic_url(url, session)

    sess = session or get_session()
    try:
        resp = sess.get(url, timeout=20)
    except requests.RequestException as e:
        logger.warning(f"Request failed for {url}: {e}")
        return None

    if resp.status_code != 200:
        logger.warning(f"HTTP {resp.status_code} for {url}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    next_data_tag = soup.find("script", id="__NEXT_DATA__")
    if not next_data_tag:
        return _parse_generic_url(url, sess, resp.text)

    try:
        data = json.loads(next_data_tag.string)
    except json.JSONDecodeError:
        return None

    # Listing detail page has the property in props.pageProps.property
    page_props = data.get("props", {}).get("pageProps", {})
    raw = page_props.get("property") or page_props.get("fetchResult", {}).get("property")

    if not raw:
        # Might be on a search page — try first result
        search = page_props.get("fetchResult", {}).get("searchFast", {})
        results = search.get("data", [])
        if results:
            raw = results[0]

    if not raw:
        logger.warning(f"No property data found in __NEXT_DATA__ for {url}")
        return None

    # Detect district from URL or address
    district = _detect_district(url, raw.get("address", ""))
    return normalize_listing(raw, district)


def _detect_district(url: str, address: str) -> str:
    """Infer our canonical district name from URL slug or address string."""
    text = (url + " " + address).lower()
    for keyword, canon in KNOWN_DISTRICTS.items():
        if keyword in text:
            return canon
    return "miraflores"  # safe default for demo


def _parse_generic_url(url: str, session=None, html: str = None) -> Optional[dict]:
    """
    Fallback parser for non-Infocasas URLs.
    Tries JSON-LD and regex extraction from visible text.
    Returns None if we can't reliably extract price + area.
    """
    sess = session or get_session()
    if html is None:
        try:
            resp = sess.get(url, timeout=20)
            html = resp.text
        except requests.RequestException:
            return None

    soup = BeautifulSoup(html, "lxml")
    result: dict = {"url": url}

    # JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            ld = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(ld, list):
            ld = ld[0] if ld else {}
        if not isinstance(ld, dict):
            continue
        offers = ld.get("offers", {})
        price = offers.get("price") or ld.get("price")
        if price:
            try:
                p = float(str(price).replace(",", ""))
                currency = offers.get("priceCurrency", "PEN")
                if currency == "PEN":
                    result["price_pen"] = p
                else:
                    result["price_usd"] = p
                result["currency"] = currency
            except ValueError:
                pass
        if not result.get("description"):
            result["description"] = ld.get("description", "")

    # Regex fallback on visible text
    text = " ".join(soup.get_text(" ", strip=True).split())

    if not result.get("price_pen"):
        m = re.search(r"S[/\.\s]+\s*([\d,]+)", text)
        if m:
            result["price_pen"] = float(m.group(1).replace(",", ""))
            result["currency"] = "PEN"

    if not result.get("area_m2"):
        m = re.search(r"(\d+(?:\.\d+)?)\s*m[²2]", text, re.IGNORECASE)
        if m:
            result["area_m2"] = float(m.group(1))

    if not result.get("bedrooms"):
        m = re.search(r"(\d+)\s*(?:dormitorio|dorm\.|habitaci[oó]n|cuarto)s?", text, re.IGNORECASE)
        if m:
            result["bedrooms"] = int(m.group(1))

    if not result.get("bathrooms"):
        m = re.search(r"(\d+)\s*(?:ba[ñn]o|ss\.?\s*hh\.?)s?", text, re.IGNORECASE)
        if m:
            result["bathrooms"] = int(m.group(1))

    # Amenities from full text
    desc = (result.get("description", "") + " " + text[:3000]).lower()
    amenities = {k: int(any(kw in desc for kw in kws)) for k, kws in AMENITY_KEYWORDS.items()}
    result["amenities_raw"] = json.dumps(amenities)

    result["district"] = _detect_district(url, result.get("address", ""))

    # Only return if we have the minimum fields for a prediction
    if result.get("price_pen") and result.get("area_m2") and result.get("bedrooms") is not None:
        return result

    return None
