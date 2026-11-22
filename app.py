"""Credit Card Fraud Detection Portal - Single Command Website Runner.

Launches the complete website and backend on http://localhost:8000.
"""
import os
import sys
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import MODEL_PATH, RESULTS_PATH
from backend.database import execute_query, init_db

def ensure_warehouse_seeded():
    """Verify warehouse is populated; trigger ETL if empty."""
    init_db()
    try:
        rows = execute_query("SELECT COUNT(*) as count FROM fact_transaction")
        count = rows[0]["count"] if rows else 0
        if count == 0:
            print("[SEED] Warehouse is empty. Executing ETL pipeline...")
            from etl.etl import run_etl
            run_etl()
        else:
            print(f"[SEED] Data warehouse verified: {count:,} transactions loaded.")
    except Exception as e:
        print(f"[SEED] Fact table check failed ({e}). Running ETL pipeline...")
        from etl.etl import run_etl
        run_etl()

def ensure_models_trained():
    """Verify model bundle exists; trigger training if missing."""
    if not Path(MODEL_PATH).exists() or not Path(RESULTS_PATH).exists():
        print("[SEED] Model artifacts missing. Training models and extracting SHAP...")
        from ml.train import train_models
        train_models()
    else:
        print(f"[SEED] Machine learning models verified ({MODEL_PATH}).")

if __name__ == "__main__":
    print("===================================================================")
    print("      Credit Card Fraud Detection Website Starting                 ")
    print("===================================================================")
    
    # 1. Verify warehouse & ML models
    ensure_warehouse_seeded()
    ensure_models_trained()

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    url = f"http://localhost:{port}"

    print(f"\n[WEBSITE READY] Access the portal in your browser at:")
    print(f"👉 {url}")
    print(f"👉 http://127.0.0.1:{port}")
    print(f"👉 {url}/docs (API Swagger documentation)\n")

    # Automatically attempt to open the user's default browser
    try:
        webbrowser.open(url)
    except Exception:
        pass

    import uvicorn
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)
