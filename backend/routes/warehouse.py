"""Warehouse Schema & Table Preview Router."""
from fastapi import APIRouter, Query, HTTPException
from backend.database import execute_query

router = APIRouter(prefix="/api/warehouse", tags=["Warehouse Schema"])

ALLOWED_TABLES = [
    "fact_transaction",
    "dim_time",
    "dim_amount_band",
    "dim_merchant",
    "dim_card",
    "etl_run_log",
    "model_registry"
]

@router.get("/preview")
def preview_table(table: str = Query("fact_transaction", description="Table name to inspect"), limit: int = Query(8, ge=1, le=50)):
    """Fetch sample rows and schema definition for an interactive warehouse table viewer."""
    if table not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail=f"Table '{table}' is not whitelisted. Allowed: {ALLOWED_TABLES}")

    # Use safe parameterized limit with whitelisted table name
    sql = f"SELECT * FROM {table} LIMIT :limit"
    rows = execute_query(sql, {"limit": limit})
    
    count_sql = f"SELECT COUNT(*) as total FROM {table}"
    total = execute_query(count_sql)[0]["total"]

    columns = list(rows[0].keys()) if rows else []

    return {
        "table": table,
        "total_records": total,
        "preview_count": len(rows),
        "columns": columns,
        "rows": rows
    }
