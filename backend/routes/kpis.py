"""KPIs and summary metrics router."""
from fastapi import APIRouter
from backend.database import execute_query

router = APIRouter(prefix="/api", tags=["KPIs"])

@router.get("/kpis")
def get_kpis():
    """Retrieve high-level portfolio KPIs and trend distributions."""
    sql = """
    SELECT 
        COUNT(*) AS total_transactions,
        SUM(is_fraud) AS fraud_transactions,
        ROUND(100.0 * SUM(is_fraud) / COUNT(*), 4) AS fraud_rate_pct,
        ROUND(SUM(amount), 2) AS total_amount,
        ROUND(SUM(CASE WHEN is_fraud = 1 THEN amount ELSE 0 END), 2) AS amount_at_risk,
        ROUND(AVG(amount), 2) AS avg_amount,
        ROUND(MAX(amount), 2) AS max_amount
    FROM fact_transaction
    """
    rows = execute_query(sql)
    kpis = rows[0] if rows else {}

    # Trend by Period
    period_sql = """
    SELECT 
        t.period,
        COUNT(*) as txns,
        SUM(f.is_fraud) as fraud,
        ROUND(100.0 * SUM(f.is_fraud) / COUNT(*), 3) as fraud_rate
    FROM fact_transaction f
    JOIN dim_time t ON f.time_key = t.time_key
    GROUP BY t.period
    ORDER BY CASE t.period 
        WHEN 'Morning' THEN 1 
        WHEN 'Afternoon' THEN 2 
        WHEN 'Evening' THEN 3 
        WHEN 'Night' THEN 4 
    END
    """
    periods = execute_query(period_sql)

    # Hourly distribution
    hourly_sql = """
    SELECT 
        t.hour,
        COUNT(*) as total_txns,
        SUM(f.is_fraud) as fraud_count
    FROM fact_transaction f
    JOIN dim_time t ON f.time_key = t.time_key
    GROUP BY t.hour
    ORDER BY t.hour
    """
    hourly = execute_query(hourly_sql)

    return {
        "kpis": kpis,
        "by_period": periods,
        "by_hour": hourly
    }
