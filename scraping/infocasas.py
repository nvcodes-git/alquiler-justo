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
    "miraflores":  "lima-miraflores",
    "san-isidro":  "lima-san-isidro",
    "surco":       "lima-surco",
    "magdalena":   "lima-magdalena-del-mar",
    "san-miguel":  "lima-san-miguel",
    "barranco":    "lima-barranco",
    "san-borja":   "lima-san-borja",
    "la-molina":   "lima-la-molina",
    "jesus-maria": "lima-jesus-maria",
    "lince":       "lima-lince",
    "pueblo-libre":"lima-pueblo-libre",
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
# District assignment by real location (address + lat/lon)
# ---------------------------------------------------------------------------

USD_TO_PEN = 3.75

# Distritos que SÍ cubrimos → slug canónico
OUR_DISTRICTS = {
    "miraflores", "san-isidro", "surco", "magdalena", "san-miguel",
    "barranco", "san-borja", "la-molina", "jesus-maria", "lince", "pueblo-libre",
}

# Gazetteer de Lima Metropolitana (slug → centroide aprox). Incluye distritos
# fuera de cobertura para poder RECHAZAR avisos que no son de los nuestros.
LIMA_GAZETTEER = {
    # cobertura
    "miraflores": (-12.1219, -77.0299), "san-isidro": (-12.0969, -77.0367),
    "surco": (-12.1477, -76.9934), "magdalena": (-12.0925, -77.0714),
    "san-miguel": (-12.0771, -77.0982), "barranco": (-12.1530, -77.0197),
    "san-borja": (-12.0990, -76.9952), "la-molina": (-12.0820, -76.9432),
    "jesus-maria": (-12.0703, -77.0469), "lince": (-12.0833, -77.0361),
    "pueblo-libre": (-12.0742, -77.0630),
    # fuera de cobertura (para rechazar correctamente)
    "surquillo": (-12.1120, -77.0180), "la-victoria": (-12.0680, -77.0160),
    "lima-cercado": (-12.0500, -77.0400), "breña": (-12.0590, -77.0500),
    "rimac": (-12.0270, -77.0300), "el-agustino": (-12.0420, -76.9930),
    "santa-anita": (-12.0430, -76.9700), "ate": (-12.0260, -76.9180),
    "san-juan-de-lurigancho": (-11.9800, -77.0000), "comas": (-11.9500, -77.0600),
    "independencia": (-11.9900, -77.0500), "los-olivos": (-11.9700, -77.0700),
    "san-martin-de-porres": (-12.0000, -77.0800), "carabayllo": (-11.8967, -77.0386),
    "puente-piedra": (-11.8700, -77.0750), "chorrillos": (-12.1700, -77.0140),
    "san-juan-de-miraflores": (-12.1600, -76.9700), "villa-el-salvador": (-12.2130, -76.9380),
    "villa-maria-del-triunfo": (-12.1620, -76.9430), "callao": (-12.0560, -77.1180),
    "ventanilla": (-11.8745, -77.1300), "bellavista": (-12.0620, -77.1080),
    "la-perla": (-12.0700, -77.1150), "lurin": (-12.2700, -76.8700),
    "pachacamac": (-12.2300, -76.8500), "chaclacayo": (-11.9800, -76.7700),
    "santiago-de-surco": (-12.1477, -76.9934),
}

# Nombres tal como aparecen en `address` → slug (incluye fuera de cobertura)
_ADDR_NAME2SLUG = {
    "miraflores": "miraflores", "san isidro": "san-isidro",
    "santiago de surco": "surco", "surco": "surco",
    "magdalena del mar": "magdalena", "magdalena": "magdalena",
    "san miguel": "san-miguel", "barranco": "barranco", "san borja": "san-borja",
    "la molina": "la-molina", "jesús maría": "jesus-maria", "jesus maria": "jesus-maria",
    "lince": "lince", "pueblo libre": "pueblo-libre",
    "surquillo": "surquillo", "la victoria": "la-victoria", "breña": "breña",
    "rímac": "rimac", "rimac": "rimac", "el agustino": "el-agustino",
    "santa anita": "santa-anita", "ate": "ate", "comas": "comas",
    "independencia": "independencia", "los olivos": "los-olivos",
    "san martín de porres": "san-martin-de-porres", "san martin de porres": "san-martin-de-porres",
    "carabayllo": "carabayllo", "puente piedra": "puente-piedra",
    "chorrillos": "chorrillos", "san juan de lurigancho": "san-juan-de-lurigancho",
    "san juan de miraflores": "san-juan-de-miraflores",
    "villa el salvador": "villa-el-salvador", "villa maría del triunfo": "villa-maria-del-triunfo",
    "callao": "callao", "ventanilla": "ventanilla", "bellavista": "bellavista",
    "la perla": "la-perla", "lurín": "lurin", "lurin": "lurin",
    "pachacámac": "pachacamac", "pachacamac": "pachacamac", "chaclacayo": "chaclacayo",
    "cercado de lima": "lima-cercado", "lima cercado": "lima-cercado",
}


def _district_from_location(address: str, lat, lon) -> Optional[str]:
    """
    Determine the real district of a listing. Returns a canonical slug if it
    is one of OUR_DISTRICTS, or None if the listing is out of coverage / unknown.
    Primary signal: district name in `address`. Fallback: nearest centroid by lat/lon.
    """
    a = (address or "").lower()
    for name, slug in _ADDR_NAME2SLUG.items():
        if re.search(r"(^|[,\s])" + re.escape(name) + r"($|[,\s])", a):
            canon = "surco" if slug == "santiago-de-surco" else slug
            return canon if canon in OUR_DISTRICTS else None

    try:
        latf, lonf = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-13 < latf < -11 and -78 < lonf < -76):
        return None  # fuera de Lima / coords inválidas

    best, best_d = None, 1e9
    for slug, (cla, clo) in LIMA_GAZETTEER.items():
        d = (cla - latf) ** 2 + (clo - lonf) ** 2
        if d < best_d:
            best_d, best = d, slug
    if best == "santiago-de-surco":
        best = "surco"
    # aceptar solo si está razonablemente cerca de algún centroide (~9 km)
    if best and best_d < 0.08 ** 2:
        return best if best in OUR_DISTRICTS else None
    return None


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
    elif price_usd:
        price_pen = float(price_usd) * USD_TO_PEN   # convertir USD→PEN
    elif price_amount and currency_name in ("US$", "USD", "$"):
        price_pen = float(price_amount) * USD_TO_PEN
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

    # District: derive from the listing's REAL location (address + lat/lon),
    # not the search slug (Infocasas search returns mixed districts).
    district = _district_from_location(
        raw.get("address"), raw.get("latitude"), raw.get("longitude")
    )
    if district is None:
        return None  # out of coverage / unknown → skip

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
    districts: list[str] | None = None,
) -> int:
    """Scrape target districts. Returns total new listings saved."""
    conn = init_db(db_path)
    session = get_session()
    total_new = 0

    target = {k: v for k, v in DISTRITOS.items() if districts is None or k in districts}
    for nombre, slug in target.items():
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
