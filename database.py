# database.py
import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "distressiq.db"
DB_PATH = Path(os.getenv("DISTRESSIQ_DB_PATH", str(DEFAULT_DB_PATH)))


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # Core listings table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT NOT NULL,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            source TEXT,
            source_url TEXT,
            asking_price INTEGER,
            created_at TEXT NOT NULL
        );
        """
    )
    _ensure_column(cur, "listings", "source_url", "TEXT")

    # Photos
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            FOREIGN KEY(listing_id) REFERENCES listings(id)
        );
        """
    )

    # High-level metrics (aggregated condition etc.)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_metrics (
            listing_id INTEGER PRIMARY KEY,
            overall_condition REAL,
            rehab_cost_estimate INTEGER,
            rent_estimate INTEGER,
            section8_rent INTEGER,
            net_rent INTEGER,
            cap_rate REAL,
            last_updated TEXT,
            FOREIGN KEY(listing_id) REFERENCES listings(id)
        );
        """
    )

    # Mechanical analysis
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_mechanical_analysis (
            listing_id INTEGER PRIMARY KEY,
            plumbing_condition REAL,
            water_heater_condition REAL,
            furnace_condition REAL,
            boiler_condition REAL,
            mechanical_rehab_cost INTEGER,
            last_updated TEXT,
            FOREIGN KEY(listing_id) REFERENCES listings(id)
        );
        """
    )

    # Room (kitchen/bath) analysis
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_room_analysis (
            listing_id INTEGER PRIMARY KEY,
            kitchen_condition REAL,
            kitchen_rehab_cost INTEGER,
            bathroom_condition REAL,
            bathroom_rehab_cost INTEGER,
            last_updated TEXT,
            FOREIGN KEY(listing_id) REFERENCES listings(id)
        );
        """
    )

    # Occupancy analysis
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_occupancy_analysis (
            listing_id INTEGER PRIMARY KEY,
            is_occupied INTEGER,
            occupancy_confidence REAL,
            last_occupied_estimate TEXT,
            risk_flags_json TEXT,
            last_updated TEXT,
            FOREIGN KEY(listing_id) REFERENCES listings(id)
        );
        """
    )

    # Owner / distress analysis
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_owner_analysis (
            listing_id INTEGER PRIMARY KEY,
            owner_name TEXT,
            owner_mailing_address TEXT,
            last_sale_date TEXT,
            last_sale_price INTEGER,
            tax_status TEXT,
            tax_balance INTEGER,
            owns_other_properties INTEGER,
            owner_distress_score REAL,
            last_updated TEXT,
            FOREIGN KEY(listing_id) REFERENCES listings(id)
        );
        """
    )

    # Market / inventory analysis
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_market_analysis (
            listing_id INTEGER PRIMARY KEY,
            zip_code TEXT,
            inventory_count INTEGER,
            distressed_inventory INTEGER,
            inventory_trend TEXT,
            competition_score REAL,
            last_updated TEXT,
            FOREIGN KEY(listing_id) REFERENCES listings(id)
        );
        """
    )

    # Comps
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS comps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_listing_id INTEGER NOT NULL,
            address TEXT,
            price INTEGER,
            sold_date TEXT,
            beds INTEGER,
            baths REAL,
            sqft INTEGER,
            distance_miles REAL,
            condition_score REAL,
            distress_type TEXT,
            source TEXT,
            FOREIGN KEY(subject_listing_id) REFERENCES listings(id)
        );
        """
    )

    # Offers
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_offers (
            listing_id INTEGER PRIMARY KEY,
            recommended_offer INTEGER,
            mao INTEGER,
            rent_value INTEGER,
            distress_discount REAL,
            condition_discount REAL,
            market_pressure_discount REAL,
            final_score REAL,
            generated_at TEXT,
            FOREIGN KEY(listing_id) REFERENCES listings(id)
        );
        """
    )

    # Truth layer: what we know, from where, with what confidence
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS truth_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,   -- e.g. 'listing', 'comp'
            entity_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            value TEXT,
            source TEXT,                 -- 'county', 'hud', 'photo_model', etc.
            confidence REAL,             -- 0.0 - 1.0
            value_type TEXT,             -- 'fact', 'estimate', 'unknown'
            created_at TEXT NOT NULL
        );
        """
    )

    # Layman explanations
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_explanations (
            listing_id INTEGER PRIMARY KEY,
            explanation_text TEXT,
            created_at TEXT,
            FOREIGN KEY(listing_id) REFERENCES listings(id)
        );
        """
    )

    conn.commit()
    conn.close()


def insert_listing(
    address,
    city=None,
    state=None,
    zip_code=None,
    source="manual",
    asking_price=None,
    source_url=None,
    photos=None,
):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        """
        INSERT INTO listings (address, city, state, zip_code, source, source_url, asking_price, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (address, city, state, zip_code, source, source_url, asking_price, now),
    )
    listing_id = cur.lastrowid
    _replace_listing_photos(cur, listing_id, photos or [])
    conn.commit()
    conn.close()
    return listing_id


def upsert_listing(
    address,
    city=None,
    state=None,
    zip_code=None,
    source="manual",
    asking_price=None,
    source_url=None,
    photos=None,
):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id
        FROM listings
        WHERE lower(address) = lower(?)
          AND coalesce(lower(city), '') = coalesce(lower(?), '')
          AND coalesce(lower(state), '') = coalesce(lower(?), '')
          AND coalesce(lower(source), '') = coalesce(lower(?), '')
        ORDER BY id DESC
        LIMIT 1
        """,
        (address, city, state, source),
    )
    row = cur.fetchone()

    if row:
        cur.execute(
            """
            UPDATE listings
            SET city = coalesce(?, city),
                state = coalesce(?, state),
                zip_code = coalesce(?, zip_code),
                source = coalesce(?, source),
                source_url = coalesce(?, source_url),
                asking_price = coalesce(?, asking_price)
            WHERE id = ?
            """,
            (city, state, zip_code, source, source_url, asking_price, row["id"]),
        )
        _replace_listing_photos(cur, row["id"], photos or [])
        conn.commit()
        conn.close()
        return row["id"]

    conn.close()
    return insert_listing(
        address=address,
        city=city,
        state=state,
        zip_code=zip_code,
        source=source,
        asking_price=asking_price,
        source_url=source_url,
        photos=photos or [],
    )


def _ensure_column(cur, table_name: str, column_name: str, column_type: str):
    cur.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cur.fetchall()}
    if column_name not in existing:
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def _replace_listing_photos(cur, listing_id: int, photos):
    if not photos:
        return
    cur.execute("DELETE FROM listing_photos WHERE listing_id = ?", (listing_id,))
    for photo_url in photos[:12]:
        if photo_url:
            cur.execute(
                "INSERT INTO listing_photos (listing_id, file_path) VALUES (?, ?)",
                (listing_id, photo_url),
            )


def get_all_listings(
    city: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = 100,
):
    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT * FROM listings"
    clauses = []
    params = []

    if city:
        clauses.append("lower(city) = lower(?)")
        params.append(city)
    if state:
        clauses.append("lower(state) = lower(?)")
        params.append(state)

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()
    listings = [dict(row) for row in rows]
    if listings:
        ids = [row["id"] for row in listings]
        placeholders = ",".join("?" for _ in ids)
        cur.execute(
            f"SELECT listing_id, file_path FROM listing_photos WHERE listing_id IN ({placeholders})",
            ids,
        )
        photos_by_listing = {}
        for photo in cur.fetchall():
            photos_by_listing.setdefault(photo["listing_id"], []).append(photo["file_path"])
        for row in listings:
            row["photos"] = photos_by_listing.get(row["id"], [])
    conn.close()
    return listings


if __name__ == "__main__":
    init_db()
    print("Database initialized at", DB_PATH)
