import time
import random
import sqlite3
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_last_request_time: float = 0.0

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id        TEXT,
    url               TEXT UNIQUE,
    district          TEXT,
    title             TEXT,
    price_pen         REAL,
    price_usd         REAL,
    price_raw         REAL,
    currency          TEXT,
    area_m2           REAL,
    bedrooms          INTEGER,
    bathrooms         INTEGER,
    floor             INTEGER,
    antiquity_years   INTEGER,
    address           TEXT,
    description       TEXT,
    amenities_raw     TEXT,
    days_listed       INTEGER,
    scraped_at        TEXT
);
"""


def get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "DNT": "1",
    })
    return session


def rate_limit(min_delay: float = 1.5, jitter: float = 1.0) -> None:
    global _last_request_time
    elapsed = time.time() - _last_request_time
    wait = min_delay + random.uniform(0, jitter) - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_request_time = time.time()


def init_db(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def save_listing(conn: sqlite3.Connection, listing: dict) -> bool:
    """Insert listing; return True if inserted, False if already existed."""
    columns = [
        "listing_id", "url", "district", "title",
        "price_pen", "price_usd", "price_raw", "currency",
        "area_m2", "bedrooms", "bathrooms", "floor",
        "antiquity_years", "address", "description",
        "amenities_raw", "days_listed", "scraped_at",
    ]
    vals = {col: listing.get(col) for col in columns}
    placeholders = ", ".join(f":{c}" for c in columns)
    col_names = ", ".join(columns)
    cursor = conn.execute(
        f"INSERT OR IGNORE INTO listings ({col_names}) VALUES ({placeholders})",
        vals,
    )
    conn.commit()
    return cursor.rowcount > 0


def already_scraped(conn: sqlite3.Connection, url: str) -> bool:
    cur = conn.execute("SELECT 1 FROM listings WHERE url = ?", (url,))
    return cur.fetchone() is not None
