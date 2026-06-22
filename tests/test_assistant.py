"""Tests del asistente: parseo de consultas y búsqueda."""
from pathlib import Path

from ai.assistant import parse_query_fallback, search_listings

DB = Path("data/listings.db")


def test_parse_basic_query():
    f = parse_query_fallback("2 dormitorios en Miraflores hasta S/ 3,500")
    assert f["district"] == "miraflores"
    assert f["bedrooms"] == 2
    assert f["price_max"] == 3500


def test_parse_area_range_not_confused_with_price():
    f = parse_query_fallback("depto en La Molina mínimo 100 metros")
    assert f["district"] == "la-molina"
    assert f["area_min"] == 100
    assert "price_min" not in f  # "mínimo 100 metros" no debe leerse como precio


def test_parse_price_range():
    f = parse_query_fallback("Barranco precio entre 2000 y 3000 soles")
    assert f["price_min"] == 2000
    assert f["price_max"] == 3000


def test_search_returns_matching_district():
    df = search_listings(district="surco", bedrooms=2, price_max=4000, db_path=DB)
    assert not df.empty
    assert (df["district"] == "surco").all()
    assert (df["price_pen"] <= 4000).all()
