"""AI deal hunter and market discovery engine.

V1 keeps this intentionally lean: it derives market stats from the existing
property database and rent-analysis tables, scores properties, and creates
discovery alerts for cash-flow, Section 8, foreclosure, and hidden-market
opportunities.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, Numeric, String, Table, Text, delete, desc, func, insert, select

from server.low_cost_data_engine import estimate_section8_rent
from server.property_system import _jsonable, _row_to_dict, get_property_engine, metadata, properties
from server.rent_analyzer import deal_analysis


market_stats = Table(
    "market_stats",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("city", Text),
    Column("state", Text),
    Column("zip_code", Text),
    Column("avg_price", Numeric),
    Column("median_price", Numeric),
    Column("avg_rent", Numeric),
    Column("median_rent", Numeric),
    Column("avg_section8_rent", Numeric),
    Column("vacancy_rate", Numeric),
    Column("foreclosure_rate", Numeric),
    Column("crime_score", Numeric),
    Column("appreciation_score", Numeric),
    Column("investor_activity_score", Numeric),
    Column("permit_growth_score", Numeric),
    Column("population_growth_score", Numeric),
    Column("cashflow_score", Numeric),
    Column("opportunity_score", Numeric),
    Column("discovered_by_ai", Boolean, default=False),
    Column("updated_at", DateTime, default=datetime.utcnow),
)

property_scores = Table(
    "property_scores",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("property_id", Integer, nullable=False),
    Column("cashflow_score", Numeric),
    Column("rehab_score", Numeric),
    Column("section8_score", Numeric),
    Column("neighborhood_score", Numeric),
    Column("appreciation_score", Numeric),
    Column("competition_score", Numeric),
    Column("risk_score", Numeric),
    Column("total_score", Numeric),
    Column("ai_reasoning", JSON),
    Column("created_at", DateTime, default=datetime.utcnow),
)

discovery_alerts = Table(
    "discovery_alerts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("title", Text),
    Column("description", Text),
    Column("city", Text),
    Column("state", Text),
    Column("alert_type", Text),
    Column("score", Numeric),
    Column("payload", JSON),
    Column("created_at", DateTime, default=datetime.utcnow),
)

user_preferences = Table(
    "user_preferences",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer),
    Column("max_price", Numeric),
    Column("min_roi", Numeric),
    Column("section8_enabled", Boolean, default=True),
    Column("preferred_states", JSON),
    Column("preferred_property_types", JSON),
    Column("crime_tolerance", Numeric),
    Column("rehab_tolerance", Numeric),
    Column("created_at", DateTime, default=datetime.utcnow),
)


def _num(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _median(values: list[float]) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _score_market(rows: list[Mapping[str, Any]], city: str, state: str, zip_code: str) -> dict[str, Any]:
    prices = [_num(row.get("estimated_value")) for row in rows]
    prices = [value for value in prices if value]
    rents = [_num(row.get("estimated_rent")) for row in rows]
    rents = [value for value in rents if value]
    bedrooms = [_num(row.get("bedrooms")) or 2 for row in rows]
    avg_price = sum(prices) / len(prices) if prices else 0
    avg_rent = sum(rents) / len(rents) if rents else 0
    avg_section8 = sum(estimate_section8_rent(bed, city, state) for bed in bedrooms) / len(bedrooms) if bedrooms else estimate_section8_rent(2, city, state)
    foreclosure_rate = 100 * sum(1 for row in rows if row.get("foreclosure")) / len(rows) if rows else 0
    vacancy_rate = 100 * sum(1 for row in rows if row.get("vacant")) / len(rows) if rows else 0
    investor_activity = min(10, len(rows) / 8)
    rent_to_price = (avg_rent * 12 / avg_price) if avg_price else 0
    cashflow_score = min(100, rent_to_price * 520)
    section8_bonus = max(0, (avg_section8 - avg_rent) / avg_rent * 100) if avg_rent else 0
    opportunity_score = min(100, cashflow_score + section8_bonus + max(0, 10 - investor_activity) * 2 + min(15, foreclosure_rate))
    return {
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "avg_price": round(avg_price),
        "median_price": round(_median(prices)),
        "avg_rent": round(avg_rent),
        "median_rent": round(_median(rents)),
        "avg_section8_rent": round(avg_section8),
        "vacancy_rate": round(vacancy_rate, 1),
        "foreclosure_rate": round(foreclosure_rate, 1),
        "crime_score": 5,
        "appreciation_score": 6 if opportunity_score >= 55 else 4,
        "investor_activity_score": round(investor_activity, 1),
        "permit_growth_score": 5,
        "population_growth_score": 5,
        "cashflow_score": round(cashflow_score, 1),
        "opportunity_score": round(opportunity_score, 1),
        "discovered_by_ai": opportunity_score >= 60,
        "updated_at": datetime.utcnow(),
    }


def update_market_stats() -> list[dict[str, Any]]:
    with get_property_engine().begin() as conn:
        rows = conn.execute(select(properties)).mappings().all()
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        item = _row_to_dict(row)
        key = (
            str(item.get("city") or "Unknown"),
            str(item.get("state") or ""),
            str(item.get("zip") or ""),
        )
        groups.setdefault(key, []).append(item)

    stats = [_score_market(group_rows, *key) for key, group_rows in groups.items() if key[1]]
    with get_property_engine().begin() as conn:
        conn.execute(delete(market_stats))
        for stat in stats:
            conn.execute(insert(market_stats).values(**stat))
    return [_jsonable(stat) for stat in sorted(stats, key=lambda item: item["opportunity_score"], reverse=True)]


def calculate_property_ai_score(property_data: Mapping[str, Any], market: Mapping[str, Any], rent_analysis: Mapping[str, Any]) -> dict[str, Any]:
    reasons = []
    price = _num(property_data.get("estimated_value")) or 0
    rent = _num(rent_analysis.get("estimated_rent") or property_data.get("estimated_rent")) or 0
    section8 = _num(rent_analysis.get("section8_rent") or market.get("avg_section8_rent")) or 0
    market_avg_price = _num(market.get("avg_price")) or price
    investor_activity = _num(market.get("investor_activity_score")) or 5
    appreciation = _num(market.get("appreciation_score")) or 5
    vacancy = _num(market.get("vacancy_rate")) or 10

    cashflow_score = 0
    section8_score = 0
    neighborhood_score = 45
    appreciation_score = appreciation * 10
    competition_score = max(0, (10 - investor_activity) * 10)
    risk_score = 25

    if price and market_avg_price and price < market_avg_price * 0.65:
        reasons.append("Price significantly below market average")
        cashflow_score += 20
    if price and rent:
        rent_ratio = rent / price
        if rent_ratio > 0.02:
            reasons.append("Strong rent-to-price ratio")
            cashflow_score += 25
        elif rent_ratio > 0.015:
            cashflow_score += 15
    if section8 and rent and section8 > rent:
        reasons.append("Section 8 rents exceed market rent")
        section8_score += 15
    if investor_activity < 4:
        reasons.append("Low investor competition")
        competition_score += 15
    if appreciation > 7:
        reasons.append("Neighborhood appreciation improving")
    if vacancy < 5:
        reasons.append("Vacancy rates improving")
        neighborhood_score += 10
    if property_data.get("foreclosure") or property_data.get("tax_delinquent"):
        reasons.append("Distress indicator may create acquisition leverage")
        risk_score += 10

    total_score = min(100, cashflow_score + section8_score + (neighborhood_score * 0.2) + (appreciation_score * 0.1) + (competition_score * 0.15) - (risk_score * 0.12))
    return {
        "property_id": property_data["id"],
        "cashflow_score": round(cashflow_score, 1),
        "rehab_score": 50,
        "section8_score": round(section8_score, 1),
        "neighborhood_score": round(neighborhood_score, 1),
        "appreciation_score": round(appreciation_score, 1),
        "competition_score": round(competition_score, 1),
        "risk_score": round(risk_score, 1),
        "total_score": round(max(0, total_score), 1),
        "ai_reasoning": {"reasons": reasons or ["Score uses price, rent, Section 8, competition, and market momentum signals."]},
        "created_at": datetime.utcnow(),
    }


def calculate_all_property_scores() -> list[dict[str, Any]]:
    with get_property_engine().begin() as conn:
        property_rows = conn.execute(select(properties)).mappings().all()
        stat_rows = conn.execute(select(market_stats)).mappings().all()
        rent_rows = conn.execute(select(deal_analysis).order_by(desc(deal_analysis.c.updated_at))).mappings().all()

    market_by_key = {(row.get("city"), row.get("state"), row.get("zip_code")): _row_to_dict(row) for row in stat_rows}
    rent_by_property: dict[int, dict[str, Any]] = {}
    for row in rent_rows:
        item = _row_to_dict(row)
        rent_by_property.setdefault(int(item["property_id"]), item)

    scores = []
    for row in property_rows:
        property_data = _row_to_dict(row)
        key = (property_data.get("city"), property_data.get("state"), property_data.get("zip"))
        market = market_by_key.get(key) or {}
        scores.append(calculate_property_ai_score(property_data, market, rent_by_property.get(int(property_data["id"]), {})))

    with get_property_engine().begin() as conn:
        conn.execute(delete(property_scores))
        for score in scores:
            conn.execute(insert(property_scores).values(**score))
    return [_jsonable(score) for score in sorted(scores, key=lambda item: item["total_score"], reverse=True)]


def run_market_discovery() -> dict[str, Any]:
    stats = update_market_stats()
    scores = calculate_all_property_scores()
    alerts = []
    for market in stats:
        reasons = []
        avg_price = _num(market.get("avg_price")) or 0
        avg_rent = _num(market.get("avg_rent")) or 0
        section8 = _num(market.get("avg_section8_rent")) or 0
        rent_to_price = (avg_rent * 12 / avg_price) if avg_price else 0
        if rent_to_price > 0.018 and (_num(market.get("investor_activity_score")) or 10) < 5 and (_num(market.get("vacancy_rate")) or 10) < 8:
            reasons.append("Strong cash flow with low competition")
        if avg_rent and section8 > avg_rent * 1.15:
            reasons.append("Section 8 arbitrage opportunity")
        if (_num(market.get("foreclosure_rate")) or 0) > 7 and (_num(market.get("investor_activity_score")) or 10) < 4:
            reasons.append("Foreclosure inventory increasing")
        if not reasons and (_num(market.get("opportunity_score")) or 0) >= 60:
            reasons.append("AI hidden market score crossed opportunity threshold")
        for reason in reasons:
            alerts.append(
                {
                    "title": "AI Market Discovery",
                    "description": reason,
                    "city": market.get("city"),
                    "state": market.get("state"),
                    "alert_type": "ai_hidden_market" if "hidden" in reason.lower() else "market_opportunity",
                    "score": market.get("opportunity_score"),
                    "payload": {"market": market, "reasons": reasons},
                    "created_at": datetime.utcnow(),
                }
            )

    with get_property_engine().begin() as conn:
        conn.execute(delete(discovery_alerts))
        for alert in alerts:
            conn.execute(insert(discovery_alerts).values(**alert))

    return {
        "success": True,
        "markets": stats[:25],
        "property_scores": scores[:50],
        "alerts": [_jsonable(alert) for alert in sorted(alerts, key=lambda item: item["score"] or 0, reverse=True)[:50]],
    }


def get_market_stats(limit: int = 50) -> list[dict[str, Any]]:
    with get_property_engine().begin() as conn:
        rows = conn.execute(select(market_stats).order_by(desc(market_stats.c.opportunity_score)).limit(limit)).mappings().all()
    return [_row_to_dict(row) for row in rows]


def get_discovery_alerts(limit: int = 50) -> list[dict[str, Any]]:
    with get_property_engine().begin() as conn:
        rows = conn.execute(select(discovery_alerts).order_by(desc(discovery_alerts.c.score), desc(discovery_alerts.c.created_at)).limit(limit)).mappings().all()
    return [_row_to_dict(row) for row in rows]
