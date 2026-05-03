# backend.py
from datetime import datetime
from typing import Optional, Dict, Any, List

from database import (
    get_connection,
    init_db,
    insert_listing,
)


# ---------- Truth-layer helpers ----------

def add_truth_item(entity_type: str, entity_id: int, field_name: str,
                   value: Optional[str], source: str,
                   confidence: float, value_type: str):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        """
        INSERT INTO truth_items (entity_type, entity_id, field_name, value, source, confidence, value_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (entity_type, entity_id, field_name, value, source, confidence, value_type, now),
    )
    conn.commit()
    conn.close()


# ---------- Simple data access ----------

def get_all_listings() -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM listings ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_listing(listing_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# ---------- Placeholder analysis functions ----------
# These are honest: they do NOT invent data.
# They either return None (unknown) or very simple logic.

def analyze_mechanical(listing_id: int) -> None:
    """
    Placeholder: in a real version, this would inspect photos and metadata.
    For now, we store NULLs and mark truth as 'unknown'.
    """
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()

    cur.execute(
        """
        INSERT OR REPLACE INTO listing_mechanical_analysis (
            listing_id, plumbing_condition, water_heater_condition,
            furnace_condition, boiler_condition, mechanical_rehab_cost, last_updated
        ) VALUES (?, NULL, NULL, NULL, NULL, NULL, ?)
        """,
        (listing_id, now),
    )
    conn.commit()
    conn.close()

    # Truth-layer entries
    for field in ["plumbing_condition", "water_heater_condition", "furnace_condition", "boiler_condition"]:
        add_truth_item(
            entity_type="listing",
            entity_id=listing_id,
            field_name=field,
            value=None,
            source="analysis_placeholder",
            confidence=0.0,
            value_type="unknown",
        )


def analyze_rooms(listing_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        """
        INSERT OR REPLACE INTO listing_room_analysis (
            listing_id, kitchen_condition, kitchen_rehab_cost,
            bathroom_condition, bathroom_rehab_cost, last_updated
        ) VALUES (?, NULL, NULL, NULL, NULL, ?)
        """,
        (listing_id, now),
    )
    conn.commit()
    conn.close()

    for field in ["kitchen_condition", "bathroom_condition"]:
        add_truth_item(
            entity_type="listing",
            entity_id=listing_id,
            field_name=field,
            value=None,
            source="analysis_placeholder",
            confidence=0.0,
            value_type="unknown",
        )


def analyze_occupancy(listing_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        """
        INSERT OR REPLACE INTO listing_occupancy_analysis (
            listing_id, is_occupied, occupancy_confidence,
            last_occupied_estimate, risk_flags_json, last_updated
        ) VALUES (?, NULL, NULL, NULL, NULL, ?)
        """,
        (listing_id, now),
    )
    conn.commit()
    conn.close()

    add_truth_item(
        entity_type="listing",
        entity_id=listing_id,
        field_name="occupancy",
        value=None,
        source="analysis_placeholder",
        confidence=0.0,
        value_type="unknown",
    )


def analyze_owner(listing_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        """
        INSERT OR REPLACE INTO listing_owner_analysis (
            listing_id, owner_name, owner_mailing_address,
            last_sale_date, last_sale_price, tax_status,
            tax_balance, owns_other_properties, owner_distress_score, last_updated
        ) VALUES (?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?)
        """,
        (listing_id, now),
    )
    conn.commit()
    conn.close()

    for field in ["owner_name", "tax_status", "owner_distress_score"]:
        add_truth_item(
            entity_type="listing",
            entity_id=listing_id,
            field_name=field,
            value=None,
            source="analysis_placeholder",
            confidence=0.0,
            value_type="unknown",
        )


def analyze_market(listing_id: int, zip_code: Optional[str]) -> None:
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        """
        INSERT OR REPLACE INTO listing_market_analysis (
            listing_id, zip_code, inventory_count,
            distressed_inventory, inventory_trend,
            competition_score, last_updated
        ) VALUES (?, ?, NULL, NULL, NULL, NULL, ?)
        """,
        (listing_id, zip_code, now),
    )
    conn.commit()
    conn.close()

    add_truth_item(
        entity_type="listing",
        entity_id=listing_id,
        field_name="inventory_count",
        value=None,
        source="analysis_placeholder",
        confidence=0.0,
        value_type="unknown",
    )


def analyze_metrics_basic(listing_id: int) -> None:
    """
    Very basic metrics: we only know asking_price for now.
    """
    listing = get_listing(listing_id)
    if not listing:
        return

    asking_price = listing.get("asking_price")
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()

    cur.execute(
        """
        INSERT OR REPLACE INTO listing_metrics (
            listing_id, overall_condition, rehab_cost_estimate,
            rent_estimate, section8_rent, net_rent, cap_rate, last_updated
        ) VALUES (?, NULL, NULL, NULL, NULL, NULL, NULL, ?)
        """,
        (listing_id, now),
    )
    conn.commit()
    conn.close()

    if asking_price is not None:
        add_truth_item(
            entity_type="listing",
            entity_id=listing_id,
            field_name="asking_price",
            value=str(asking_price),
            source=listing.get("source") or "manual",
            confidence=1.0,
            value_type="fact",
        )


# ---------- Offer engine (simple, honest version) ----------

def compute_offer(listing_id: int) -> None:
    """
    Simple, honest offer:
    - If we only know asking_price, we propose a conservative discount.
    - If we know nothing, we refuse to compute.
    """
    listing = get_listing(listing_id)
    if not listing:
        return

    asking_price = listing.get("asking_price")
    if asking_price is None:
        # Not enough info to compute an offer
        conn = get_connection()
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT OR REPLACE INTO listing_offers (
                listing_id, recommended_offer, mao, rent_value,
                distress_discount, condition_discount, market_pressure_discount,
                final_score, generated_at
            ) VALUES (?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?)
            """,
            (listing_id, now),
        )
        conn.commit()
        conn.close()
        return

    # For now: simple rule-of-thumb: offer 60% of asking as a placeholder.
    # This is clearly an estimate and will be labeled as such.
    recommended_offer = int(asking_price * 0.6)
    mao = None
    rent_value = None
    distress_discount = None
    condition_discount = None
    market_pressure_discount = None
    final_score = None

    conn = get_connection()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        """
        INSERT OR REPLACE INTO listing_offers (
            listing_id, recommended_offer, mao, rent_value,
            distress_discount, condition_discount, market_pressure_discount,
            final_score, generated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            listing_id,
            recommended_offer,
            mao,
            rent_value,
            distress_discount,
            condition_discount,
            market_pressure_discount,
            final_score,
            now,
        ),
    )
    conn.commit()
    conn.close()

    add_truth_item(
        entity_type="listing",
        entity_id=listing_id,
        field_name="recommended_offer",
        value=str(recommended_offer),
        source="simple_rule_of_thumb",
        confidence=0.4,
        value_type="estimate",
    )


# ---------- Layman explanation ----------

def generate_layman_explanation(listing_id: int) -> str:
    listing = get_listing(listing_id)
    if not listing:
        return "No listing found."

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM listing_offers WHERE listing_id = ?", (listing_id,))
    offer_row = cur.fetchone()

    asking_price = listing.get("asking_price")
    address = listing.get("address") or "Unknown address"

    if not offer_row or offer_row["recommended_offer"] is None:
        explanation = (
            f"For {address}, we don't have enough information to suggest an offer yet.\n"
            f"If you add more data (photos, rents, taxes, comps), the system can generate a better estimate."
        )
    else:
        recommended_offer = offer_row["recommended_offer"]
        explanation = (
            f"Property: {address}\n\n"
            f"- Asking price: ${asking_price:,} (provided)\n"
            f"- Suggested offer (rough estimate): ${recommended_offer:,}\n\n"
            f"This offer is based on a simple rule-of-thumb (about 60% of asking price).\n"
            f"It does NOT yet include real analysis of condition, rents, taxes, or comps.\n"
            f"As more data is added, this number will become more accurate and fully explained."
        )

    # Store explanation
    now = datetime.utcnow().isoformat()
    cur.execute(
        """
        INSERT OR REPLACE INTO listing_explanations (listing_id, explanation_text, created_at)
        VALUES (?, ?, ?)
        """,
        (listing_id, explanation, now),
    )
    conn.commit()
    conn.close()
    return explanation


# ---------- Orchestrator ----------

def run_full_analysis(listing_id: int) -> str:
    listing = get_listing(listing_id)
    if not listing:
        return "Listing not found."

    analyze_mechanical(listing_id)
    analyze_rooms(listing_id)
    analyze_occupancy(listing_id)
    analyze_owner(listing_id)
    analyze_market(listing_id, listing.get("zip_code"))
    analyze_metrics_basic(listing_id)
    compute_offer(listing_id)
    explanation = generate_layman_explanation(listing_id)
    return explanation


if __name__ == "__main__":
    init_db()
    # Simple smoke test
    lid = insert_listing("123 Test St", "Testville", "NY", "12345", asking_price=50000)
    print("Created listing", lid)
    print(run_full_analysis(lid))
