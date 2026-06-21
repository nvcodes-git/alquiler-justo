"""
CLI entry point to run the real estate scraper.

Usage:
    python -m scraping.run
    python -m scraping.run --max 150 --db data/raw/listings.db
"""

import argparse
import logging
import sqlite3

from scraping.infocasas import run_scraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)


def print_summary(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    by_distrito = conn.execute(
        "SELECT district, COUNT(*), ROUND(AVG(price_pen),0), ROUND(AVG(area_m2),1) "
        "FROM listings WHERE price_pen IS NOT NULL "
        "GROUP BY district ORDER BY 2 DESC"
    ).fetchall()
    conn.close()

    print(f"\n{'─'*60}")
    print(f"  Total listings in DB: {total}")
    print(f"  {'District':<20} {'Count':>6}  {'Avg S/':>8}  {'Avg m²':>7}")
    print(f"{'─'*60}")
    for row in by_distrito:
        district, count, avg_pen, avg_m2 = row
        print(f"  {(district or 'unknown'):<20} {count:>6}  {avg_pen or '-':>8}  {avg_m2 or '-':>7}")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    from scraping.infocasas import DISTRITOS
    parser = argparse.ArgumentParser(description="Scrape Lima rental listings")
    parser.add_argument("--max", type=int, default=200, help="Max listings per district")
    parser.add_argument("--db", type=str, default="data/raw/listings.db", help="SQLite DB path")
    parser.add_argument(
        "--districts", nargs="+", default=None,
        help="Subset of districts to scrape (default: all). E.g. --districts miraflores surco",
    )
    args = parser.parse_args()

    districts = args.districts or list(DISTRITOS.keys())
    print(f"Starting scraper → {args.db}  (max {args.max}/district × {len(districts)} districts)")
    total = run_scraper(db_path=args.db, max_per_distrito=args.max, districts=districts)
    print(f"\nDone. {total} new listings inserted.")
    print_summary(args.db)
