"""ETL Execution Log and Pipeline Management Router."""
from fastapi import APIRouter, BackgroundTasks
from backend.database import execute_query

router = APIRouter(prefix="/api", tags=["ETL"])

@router.get("/etl-runs")
def get_etl_runs():
    """Retrieve audit history of all ETL warehouse loads."""
    sql = """
    SELECT 
        run_id,
        run_timestamp,
        status,
        rows_extracted,
        rows_loaded,
        rows_rejected,
        fraud_rows,
        duration_seconds,
        data_quality_passed,
        notes
    FROM etl_run_log
    ORDER BY run_id DESC
    LIMIT 20
    """
    runs = execute_query(sql)
    return {
        "total_runs": len(runs),
        "latest_run": runs[0] if runs else None,
        "history": runs
    }

@router.post("/etl/trigger")
def trigger_etl(background_tasks: BackgroundTasks):
    """Trigger an asynchronous ETL pipeline re-run."""
    from etl.etl import run_etl
    background_tasks.add_task(run_etl)
    return {"message": "ETL job scheduled in background."}
