"""
Returns the 5 most similar listings to a given query from the training set.
Used in the Streamlit UI to show evidence behind the verdict.
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

DB_PATH = Path("data/raw/listings.db")


def get_comparables(
    district: str,
    area_m2: float,
    bedrooms: int,
    listed_price_pen: float,
    db_path: Path = DB_PATH,
    n: int = 5,
) -> pd.DataFrame:
    """
    Fetch the n most comparable listings from the DB.
    Similarity = same district + bedrooms within ±1, area within ±30%.
    Sorted by closeness in area to the query listing.
    """
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("""
        SELECT listing_id, url, district, price_pen, area_m2, bedrooms, bathrooms, floor, title
        FROM listings
        WHERE price_pen IS NOT NULL
          AND price_pen > 300
          AND area_m2 IS NOT NULL
          AND bedrooms IS NOT NULL
          AND district = ?
    """, conn, params=(district,))
    conn.close()

    if df.empty:
        return pd.DataFrame()

    # Filter by similar bedrooms and area
    mask = (
        (df["bedrooms"].between(max(0, bedrooms - 1), bedrooms + 1)) &
        (df["area_m2"].between(area_m2 * 0.70, area_m2 * 1.30))
    )
    filtered = df[mask].copy()

    # Fallback: relax area constraint if too few
    if len(filtered) < n:
        filtered = df[df["bedrooms"].between(max(0, bedrooms - 1), bedrooms + 1)].copy()

    if filtered.empty:
        filtered = df.copy()

    # Sort by area similarity
    filtered["area_diff"] = (filtered["area_m2"] - area_m2).abs()
    filtered = filtered.sort_values("area_diff").head(n)

    # Add price difference vs the listed price
    filtered["diff_vs_aviso_pct"] = (
        (filtered["price_pen"] - listed_price_pen) / listed_price_pen * 100
    ).round(1)

    return filtered[["listing_id", "url", "district", "price_pen", "area_m2",
                      "bedrooms", "bathrooms", "floor", "diff_vs_aviso_pct", "title"]].reset_index(drop=True)
