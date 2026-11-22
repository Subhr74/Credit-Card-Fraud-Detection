"""OLAP Explorer Router: Roll-up, Drill-down, Slice and Dice with parameterized queries."""
import csv
import io
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from backend.database import execute_query

router = APIRouter(prefix="/api", tags=["OLAP"])

# Whitelisted Group-By Dimension Attributes (No raw SQL allowed from user input)
GROUPS = {
    "period": ("t.period", "Time Period"),
    "day": ("t.day", "Day of Dataset"),
    "hour": ("t.hour", "Hour of Day (0-23)"),
    "time_key": ("t.time_key", "Elapsed Hour Index (0-47)"),
    "merchant": ("m.category", "Merchant Category"),
    "merchant_risk": ("m.risk_level", "Merchant Risk Tier"),
    "card": ("c.card_type", "Card Type"),
    "network": ("c.network", "Card Network"),
    "amount_band": ("b.band_name", "Amount Band"),
}

# Whitelisted Slice/Dice Filter Column Mapping
FILTERS = {
    "merchant": "m.category",
    "card": "c.card_type",
    "day": "t.day",
    "period": "t.period",
    "amount_band": "b.band_name",
}

FROM_CLAUSE = """
FROM fact_transaction f
JOIN dim_time t ON f.time_key = t.time_key
JOIN dim_amount_band b ON (f.band_key = b.band_key)
JOIN dim_merchant m ON f.merchant_key = m.merchant_key
JOIN dim_card c ON f.card_key = c.card_key
"""

@router.get("/dims")
def get_dimensions():
    """Return distinct dimension attributes for filter dropdowns."""
    merchants = execute_query("SELECT category FROM dim_merchant ORDER BY category")
    cards = execute_query("SELECT card_type FROM dim_card ORDER BY card_type")
    bands = execute_query("SELECT band_name FROM dim_amount_band ORDER BY band_key")
    days = execute_query("SELECT DISTINCT day FROM dim_time ORDER BY day")
    periods = ["Morning", "Afternoon", "Evening", "Night"]

    return {
        "merchants": [r["category"] for r in merchants],
        "cards": [r["card_type"] for r in cards],
        "amount_bands": [r["band_name"] for r in bands],
        "days": [r["day"] for r in days],
        "periods": periods,
        "available_groupings": [{"id": k, "label": v[1]} for k, v in GROUPS.items()]
    }

def build_olap_query(group: str, merchant: str = None, card: str = None,
                     day: int = None, period: str = None, amount_band: str = None):
    """Build secure parameterized OLAP query."""
    if group not in GROUPS:
        group = "period"

    group_col, group_label = GROUPS[group]
    where_clauses = []
    params = {}

    if merchant and not hasattr(merchant, "default"):
        where_clauses.append("m.category = :merchant")
        params["merchant"] = str(merchant)
    if card and not hasattr(card, "default"):
        where_clauses.append("c.card_type = :card")
        params["card"] = str(card)
    if day is not None and not hasattr(day, "default") and str(day).strip() != "":
        where_clauses.append("t.day = :day")
        params["day"] = int(day)
    if period and not hasattr(period, "default"):
        where_clauses.append("t.period = :period")
        params["period"] = str(period)
    if amount_band and not hasattr(amount_band, "default"):
        where_clauses.append("b.band_name = :amount_band")
        params["amount_band"] = str(amount_band)

    where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    sql = f"""
    SELECT 
        {group_col} AS label,
        COUNT(*) AS total_txns,
        SUM(f.is_fraud) AS fraud_txns,
        ROUND(100.0 * SUM(f.is_fraud) / COUNT(*), 4) AS fraud_rate_pct,
        ROUND(SUM(f.amount), 2) AS total_amount,
        ROUND(SUM(CASE WHEN f.is_fraud = 1 THEN f.amount ELSE 0 END), 2) AS amount_at_risk,
        ROUND(AVG(f.amount), 2) AS avg_amount
    {FROM_CLAUSE}
    {where_str}
    GROUP BY {group_col}
    ORDER BY total_txns DESC
    """
    return sql, params, group_label

@router.get("/olap")
def run_olap(
    group: str = "period",
    merchant: str = None,
    card: str = None,
    day: int = None,
    period: str = None,
    amount_band: str = None
):
    """Execute OLAP multi-dimensional query with roll-up, drill-down, slice and dice."""
    # Handle Query objects if invoked via dependency injection
    if hasattr(day, "default"): day = None
    if hasattr(merchant, "default"): merchant = None
    if hasattr(card, "default"): card = None
    if hasattr(period, "default"): period = None
    if hasattr(amount_band, "default"): amount_band = None
    if hasattr(group, "default"): group = "period"

    sql, params, group_label = build_olap_query(group, merchant, card, day, period, amount_band)
    rows = execute_query(sql, params)
    return {
        "group_by": group,
        "group_label": group_label,
        "filters_applied": {k: v for k, v in {"merchant": merchant, "card": card, "day": day, "period": period, "amount_band": amount_band}.items() if v is not None},
        "row_count": len(rows),
        "data": rows
    }

@router.get("/olap/export")
def export_olap_csv(
    group: str = "period",
    merchant: str = None,
    card: str = None,
    day: int = None,
    period: str = None,
    amount_band: str = None
):
    """Export the OLAP query results as a downloadable CSV."""
    sql, params, _ = build_olap_query(group, merchant, card, day, period, amount_band)
    rows = execute_query(sql, params)

    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    else:
        output.write("label,total_txns,fraud_txns,fraud_rate_pct,total_amount,amount_at_risk,avg_amount\n")

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=olap_{group}_export.csv"}
    )
