"""
Asistente conversacional de AlquilerJusto.

Dos capacidades:
  1. Búsqueda de avisos por criterios (distrito, dormitorios, m², rango de precio).
  2. Q&A sobre el mercado y la metodología (RAG: TF-IDF + Claude).

El parseo de lenguaje natural y las respuestas usan Claude; la búsqueda
en sí es una consulta SQL pura y testeable sin IA.
"""

import re
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd

DB_PATH = Path("data/listings.db")

# Canonical district name → display label (mismo set que el frontend)
DISTRICTS = {
    "miraflores": "Miraflores", "san-isidro": "San Isidro",
    "surco": "Santiago de Surco", "magdalena": "Magdalena del Mar",
    "san-miguel": "San Miguel", "barranco": "Barranco",
    "san-borja": "San Borja", "la-molina": "La Molina",
    "jesus-maria": "Jesús María", "lince": "Lince",
    "pueblo-libre": "Pueblo Libre",
}


# Keyword → canonical district (incluye variantes y acentos)
_DISTRICT_KEYWORDS = {
    "miraflores": "miraflores",
    "san isidro": "san-isidro", "sanisidro": "san-isidro",
    "surco": "surco", "santiago de surco": "surco",
    "magdalena": "magdalena",
    "san miguel": "san-miguel",
    "barranco": "barranco",
    "san borja": "san-borja",
    "la molina": "la-molina", "molina": "la-molina",
    "jesus maria": "jesus-maria", "jesús maría": "jesus-maria",
    "lince": "lince",
    "pueblo libre": "pueblo-libre",
}

_NUM = r"(\d[\d,\.]*)"


def _to_number(s: str) -> Optional[float]:
    """'3,500' o '3.500' o '3500' → 3500.0"""
    s = s.replace(",", "").replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_query_fallback(text: str) -> dict:
    """
    Deterministic parser (no AI). Extracts district, bedrooms, area and
    price filters from a Spanish natural-language query. Used as a robust
    fallback when Claude is unavailable.
    """
    t = " " + text.lower().strip() + " "
    filters: dict = {}

    # District
    for kw, canon in _DISTRICT_KEYWORDS.items():
        if kw in t:
            filters["district"] = canon
            break

    # Bedrooms: "2 dorm", "2 dormitorios", "2 cuartos", "2 habitaciones"
    m = re.search(rf"{_NUM}\s*(?:dorm|cuarto|habitaci|hab\b)", t)
    if m:
        filters["bedrooms"] = int(float(m.group(1).replace(",", "").replace(".", "")))
    elif re.search(r"\b(un|una)\s+(?:dorm|cuarto|habitaci)", t):
        filters["bedrooms"] = 1

    # ── Área ── se extrae primero y se borra del texto (los m2/metros la marcan).
    # Trabajamos sobre t_price, que va quedando "sin área" para no confundir precios.
    UNIT = r"(?:m2|m²|metros|metro)"
    t_price = t

    def _blank(span_match):
        nonlocal t_price
        s, e = span_match.span()
        t_price = t_price[:s] + " " * (e - s) + t_price[e:]

    area_range = re.search(rf"(?:entre\s+)?{_NUM}\s*(?:y|a|-)\s*{_NUM}\s*{UNIT}", t)
    if area_range:
        a, b = _to_number(area_range.group(1)), _to_number(area_range.group(2))
        if a and b:
            filters["area_min"], filters["area_max"] = min(a, b), max(a, b)
        _blank(area_range)
    else:
        m = re.search(rf"(?:m[íi]nimo|desde|m[áa]s de)\s*{_NUM}\s*{UNIT}", t)
        if m:
            filters["area_min"] = _to_number(m.group(1)); _blank(m)
        m = re.search(rf"(?:m[áa]ximo|hasta|menos de)\s*{_NUM}\s*{UNIT}", t)
        if m:
            filters["area_max"] = _to_number(m.group(1)); _blank(m)
        if "area_min" not in filters and "area_max" not in filters:
            m = re.search(rf"{_NUM}\s*{UNIT}", t)
            if m:
                center = _to_number(m.group(1))
                if center:
                    filters["area_min"] = center * 0.8
                    filters["area_max"] = center * 1.2
                _blank(m)

    # ── Precio ── se parsea sobre t_price (ya sin metrajes).
    price_ctx = re.search(rf"entre\s*(?:s/\s*)?{_NUM}\s*(?:y|a|-)\s*(?:s/\s*)?{_NUM}", t_price)
    handled_price = False
    if price_ctx:
        a, b = _to_number(price_ctx.group(1)), _to_number(price_ctx.group(2))
        if a and b:
            filters["price_min"], filters["price_max"] = min(a, b), max(a, b)
            handled_price = True
    if not handled_price:
        m = re.search(rf"(?:m[áa]ximo|hasta|menos de|por debajo de|presupuesto de?)\s*(?:s/\s*)?{_NUM}", t_price)
        if m:
            filters["price_max"] = _to_number(m.group(1))
        m = re.search(rf"(?:m[íi]nimo|desde|m[áa]s de|por encima de)\s*(?:s/\s*)?{_NUM}", t_price)
        if m:
            filters["price_min"] = _to_number(m.group(1))
        # "S/ 3500" suelto → tratar como máximo (presupuesto)
        if "price_min" not in filters and "price_max" not in filters:
            m = re.search(rf"s/\s*{_NUM}", t_price)
            if m:
                v = _to_number(m.group(1))
                if v and v >= 400:
                    filters["price_max"] = v

    return filters


_PARSE_SYSTEM = """Eres el asistente de búsqueda de AlquilerJusto, un buscador de alquileres en Lima, Perú.
Extrae los criterios de búsqueda del mensaje del usuario y devuelve ÚNICAMENTE un JSON válido, sin texto adicional.
Distritos válidos (usa exactamente estos slugs): miraflores, san-isidro, surco, magdalena, san-miguel, barranco, san-borja, la-molina, jesus-maria, lince, pueblo-libre.
Si un campo no se menciona, omítelo (no lo incluyas en el JSON)."""

_PARSE_PROMPT = """Mensaje del usuario: "{text}"

Devuelve un JSON con los campos que apliquen:
{{
  "district": "<slug de distrito o ausente>",
  "bedrooms": <entero o ausente>,
  "area_min": <número en m² o ausente>,
  "area_max": <número en m² o ausente>,
  "price_min": <número en soles o ausente>,
  "price_max": <número en soles o ausente>
}}
Ejemplo: "2 dorm en Miraflores hasta 3500 soles" → {{"district":"miraflores","bedrooms":2,"price_max":3500}}"""


def parse_query_claude(text: str) -> Optional[dict]:
    """Parse a search query with Claude. Returns None on any failure."""
    import json
    import os

    try:
        import anthropic
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        return None

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=_PARSE_SYSTEM,
            messages=[{"role": "user", "content": _PARSE_PROMPT.format(text=text)}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
        # Keep only known keys with sane values
        allowed = {"district", "bedrooms", "area_min", "area_max", "price_min", "price_max"}
        clean = {k: v for k, v in parsed.items() if k in allowed and v is not None}
        if clean.get("district") not in DISTRICTS:
            clean.pop("district", None)
        return clean or None
    except Exception:
        return None


def parse_query(text: str) -> dict:
    """
    Parse a natural-language search query into filters.
    Tries Claude first; falls back to the deterministic parser if Claude
    is unavailable or returns nothing useful.
    """
    result = parse_query_claude(text)
    if result:
        return result
    return parse_query_fallback(text)


def search_listings(
    district: Optional[str] = None,
    bedrooms: Optional[int] = None,
    area_min: Optional[float] = None,
    area_max: Optional[float] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    db_path: Path = DB_PATH,
    limit: int = 6,
) -> pd.DataFrame:
    """
    Search listings matching the given filters. All filters are optional.
    Returns up to `limit` listings sorted by price ascending.
    """
    clauses = [
        "price_pen IS NOT NULL", "price_pen > 300",
        "area_m2 IS NOT NULL", "area_m2 > 15",
    ]
    params: list = []

    if district and district in DISTRICTS:
        clauses.append("district = ?")
        params.append(district)
    if bedrooms is not None:
        # allow ±0 exact, but tolerate the listing having that many bedrooms
        clauses.append("bedrooms = ?")
        params.append(int(bedrooms))
    if area_min is not None:
        clauses.append("area_m2 >= ?")
        params.append(float(area_min))
    if area_max is not None:
        clauses.append("area_m2 <= ?")
        params.append(float(area_max))
    if price_min is not None:
        clauses.append("price_pen >= ?")
        params.append(float(price_min))
    if price_max is not None:
        clauses.append("price_pen <= ?")
        params.append(float(price_max))

    where = " AND ".join(clauses)
    sql = f"""
        SELECT listing_id, url, district, title, price_pen, area_m2,
               bedrooms, bathrooms, floor
        FROM listings
        WHERE {where}
        ORDER BY price_pen ASC
        LIMIT ?
    """
    params.append(limit)

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def relax_search(filters: dict, db_path: Path = DB_PATH, limit: int = 6) -> tuple[pd.DataFrame, list[str]]:
    """
    Try the search; if too few results, progressively relax constraints.
    Returns (results, notes) where notes explains what was relaxed.
    """
    notes: list[str] = []
    df = search_listings(**filters, db_path=db_path, limit=limit)
    if len(df) >= 1:
        return df, notes

    # Relax bedrooms (exact → ±1) by dropping it and filtering after
    relaxed = dict(filters)
    if relaxed.get("bedrooms") is not None:
        beds = relaxed.pop("bedrooms")
        notes.append(f"ampliamos la búsqueda de dormitorios alrededor de {beds}")
    df = search_listings(**relaxed, db_path=db_path, limit=limit)
    if len(df) >= 1:
        return df, notes

    # Drop area constraints
    if relaxed.get("area_min") is not None or relaxed.get("area_max") is not None:
        relaxed.pop("area_min", None)
        relaxed.pop("area_max", None)
        notes.append("relajamos el rango de metraje")
    df = search_listings(**relaxed, db_path=db_path, limit=limit)
    if len(df) >= 1:
        return df, notes

    # Drop price constraints last
    if relaxed.get("price_min") is not None or relaxed.get("price_max") is not None:
        relaxed.pop("price_min", None)
        relaxed.pop("price_max", None)
        notes.append("ampliamos el rango de precio")
    df = search_listings(**relaxed, db_path=db_path, limit=limit)
    return df, notes


if __name__ == "__main__":
    # Smoke test — no AI involved
    print("Búsqueda: 2 dorm en Miraflores, hasta S/3,500")
    res = search_listings(district="miraflores", bedrooms=2, price_max=3500)
    print(res[["district", "price_pen", "area_m2", "bedrooms"]].to_string())
    print(f"\n{len(res)} resultados")

    print("\nBúsqueda imposible (relax):")
    df, notes = relax_search({"district": "barranco", "bedrooms": 5,
                              "price_max": 1000})
    print("Notas:", notes)
    print(f"{len(df)} resultados tras relajar")
