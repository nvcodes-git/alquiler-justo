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
    "miraflores":       "miraflores",
    "san isidro":       "san-isidro",
    "san-isidro":       "san-isidro",
    "surco":            "surco",
    "santiago de surco":"surco",
    "magdalena":        "magdalena",
    "magdalena del mar":"magdalena",
    "san miguel":       "san-miguel",
    "san-miguel":       "san-miguel",
    "barranco":         "barranco",
    "san borja":        "san-borja",
    "san-borja":        "san-borja",
    "la molina":        "la-molina",
    "la-molina":        "la-molina",
    "jesus maria":      "jesus-maria",
    "jesús maría":      "jesus-maria",
    "jesus-maria":      "jesus-maria",
    "lince":            "lince",
    "pueblo libre":     "pueblo-libre",
    "pueblo-libre":     "pueblo-libre",
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

    page_props = data.get("props", {}).get("pageProps", {})

    # Individual listing page uses pageProps.data + technicalSheet
    if "data" in page_props and isinstance(page_props["data"], dict) and page_props["data"].get("id"):
        return _normalize_detail_page(page_props["data"], url)

    # Search-result page: property in pageProps.property or fetchResult.property
    raw = page_props.get("property") or page_props.get("fetchResult", {}).get("property")

    if not raw:
        search = page_props.get("fetchResult", {}).get("searchFast", {})
        results = search.get("data", [])
        if results:
            raw = results[0]

    if not raw:
        logger.warning(f"No property data found in __NEXT_DATA__ for {url}")
        return None

    district = _detect_district(url, raw.get("address", ""))
    return normalize_listing(raw, district)


USD_TO_PEN = 3.75


def _normalize_detail_page(data: dict, url: str) -> Optional[dict]:
    """Normalize the pageProps.data structure from an individual listing page."""
    ts = {item["field"]: item["value"] for item in data.get("technicalSheet", [])}

    # Area: "102 m2" → 102.0
    area_raw = ts.get("m2Built", "")
    area_m2 = None
    m = re.search(r"([\d.]+)", area_raw)
    if m:
        area_m2 = float(m.group(1))

    # Bedrooms / bathrooms / floor
    def _int(val):
        try:
            return int(str(val).strip()) if str(val).strip() else None
        except ValueError:
            return None

    bedrooms   = _int(ts.get("bedrooms"))
    bathrooms  = _int(ts.get("bathrooms")) or 1
    floor      = _int(ts.get("floor")) or 0
    garage     = _int(ts.get("garage")) or 0

    # Price
    price_info = data.get("price", {})
    amount     = price_info.get("amount")
    currency_name = price_info.get("currency", {}).get("name", "")
    price_pen = price_usd = None
    if amount:
        if "S" in currency_name and "$" not in currency_name:
            price_pen = float(amount)
            price_usd = price_pen / USD_TO_PEN
        else:
            price_usd = float(amount)
            price_pen = price_usd * USD_TO_PEN

    # District
    neighbourhood = ""
    nbhds = data.get("locations", {}).get("neighbourhood", [])
    if nbhds:
        neighbourhood = nbhds[0].get("name", "")
    district = _detect_district(url, data.get("address", "") + " " + neighbourhood)

    # Amenities from description text
    from bs4 import BeautifulSoup as _BS
    desc_html = data.get("description", "")
    desc_text = _BS(desc_html, "lxml").get_text(" ").lower()
    amenities = {k: int(any(kw in desc_text for kw in kws)) for k, kws in AMENITY_KEYWORDS.items()}
    if garage:
        amenities["cochera"] = 1

    if not (price_pen and area_m2 and bedrooms is not None):
        return None

    return {
        "listing_id": str(data.get("id", "")),
        "url":        url,
        "district":   district,
        "title":      data.get("title", ""),
        "price_pen":  round(price_pen, 0),
        "price_usd":  round(price_usd, 2) if price_usd else None,
        "currency":   "USD" if price_usd and price_pen != amount else "PEN",
        "area_m2":    area_m2,
        "bedrooms":   bedrooms,
        "bathrooms":  bathrooms,
        "floor":      floor,
        "address":    data.get("address", ""),
        "description": desc_text[:500],
        "amenities_raw": json.dumps(amenities),
    }


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
