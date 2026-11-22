"""Production ETL Pipeline for Credit Card Fraud Detection Data Warehouse.

Extracts Kaggle creditcard.csv, transforms into a star schema with simulated
merchant and card dimensions, validates data quality, and loads idempotently.
"""

import sys
import time
import datetime
import numpy as np
import pandas as pd
from pathlib import Path
from sqlalchemy import text

# Add parent directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import CSV_PATH, RANDOM_SEED
from backend.database import engine, init_db

# Dimension definitions
MERCHANTS = [
    {"merchant_key": 1, "category": "Grocery", "risk_level": "Low"},
    {"merchant_key": 2, "category": "Electronics", "risk_level": "High"},
    {"merchant_key": 3, "category": "Travel", "risk_level": "High"},
    {"merchant_key": 4, "category": "Restaurants", "risk_level": "Medium"},
    {"merchant_key": 5, "category": "Fashion", "risk_level": "Medium"},
    {"merchant_key": 6, "category": "Online Services", "risk_level": "High"},
    {"merchant_key": 7, "category": "Fuel", "risk_level": "Low"},
    {"merchant_key": 8, "category": "Healthcare", "risk_level": "Low"},
]

CARDS = [
    {"card_key": 1, "card_type": "Visa Debit", "network": "Visa"},
    {"card_key": 2, "card_type": "Visa Credit", "network": "Visa"},
    {"card_key": 3, "card_type": "Mastercard Debit", "network": "Mastercard"},
    {"card_key": 4, "card_type": "Mastercard Credit", "network": "Mastercard"},
    {"card_key": 5, "card_type": "RuPay", "network": "RuPay"},
]

AMOUNT_BANDS = [
    {"band_key": 1, "band_name": "Micro (<$10)", "min_amount": 0.0, "max_amount": 10.0},
    {"band_key": 2, "band_name": "Low ($10-$50)", "min_amount": 10.01, "max_amount": 50.0},
    {"band_key": 3, "band_name": "Medium ($50-$200)", "min_amount": 50.01, "max_amount": 200.0},
    {"band_key": 4, "band_name": "High ($200-$1,000)", "min_amount": 200.01, "max_amount": 1000.0},
    {"band_key": 5, "band_name": "Jumbo ($1,000+)", "min_amount": 1000.01, "max_amount": 999999.0},
]


class DataQualityError(Exception):
    """Raised when ETL data quality checks fail."""
    pass


def extract(csv_path: str = CSV_PATH) -> pd.DataFrame:
    """Extract raw transaction data from CSV file."""
    print(f"[{datetime.datetime.now().isoformat()}] EXTRACT: Reading {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"-> Extracted {len(df):,} raw records.")
    return df


def transform(raw_df: pd.DataFrame):
    """Clean data, derive star-schema dimension keys and attributes."""
    print(f"[{datetime.datetime.now().isoformat()}] TRANSFORM: Cleaning and transforming data...")
    initial_count = len(raw_df)

    # 1. Deduplication & Null Removal
    df = raw_df.drop_duplicates().dropna().reset_index(drop=True)
    rejected_count = initial_count - len(df)
    print(f"-> Removed {rejected_count:,} duplicate/null rows ({len(df):,} remaining).")

    # 2. Assign unique Transaction Surrogate Key
    df["txn_id"] = df.index + 1

    # 3. Derive Time Dimension Keys
    # Dataset Time is seconds elapsed from first txn (up to ~172,792s = 48 hours)
    df["time_key"] = (df["Time"] // 3600).astype(int)

    # 4. Amount Band Key
    # Cut into 5 distinct bands matching dim_amount_band
    df["band_key"] = pd.cut(
        df["Amount"],
        bins=[-np.inf, 10.0, 50.0, 200.0, 1000.0, np.inf],
        labels=[1, 2, 3, 4, 5]
    ).astype(int)

    # 5. Simulated Dimensions (Merchant and Card) with FIXED RANDOM SEED
    # Dataset does not have merchant or card info, so we simulate them deterministically.
    rng = np.random.default_rng(RANDOM_SEED)
    df["merchant_key"] = rng.integers(1, len(MERCHANTS) + 1, size=len(df))
    df["card_key"] = rng.integers(1, len(CARDS) + 1, size=len(df))

    # Build Dimension DataFrames
    hours = sorted(df["time_key"].unique())
    dim_time = pd.DataFrame({
        "time_key": hours,
        "day": [(h // 24) + 1 for h in hours],
        "hour": [h % 24 for h in hours],
    })
    dim_time["period"] = pd.cut(
        dim_time["hour"],
        bins=[-1, 5, 11, 17, 23],
        labels=["Night", "Morning", "Afternoon", "Evening"]
    ).astype(str)

    dim_band = pd.DataFrame(AMOUNT_BANDS)
    dim_merchant = pd.DataFrame(MERCHANTS)
    dim_card = pd.DataFrame(CARDS)

    # Build Fact Table
    v_cols = [f"V{i}" for i in range(1, 29)]
    fact = df[["txn_id", "time_key", "band_key", "merchant_key", "card_key", "Amount", "Class"] + v_cols].copy()
    fact = fact.rename(columns={"Amount": "amount", "Class": "is_fraud"})
    fact["predicted_probability"] = None

    return fact, dim_time, dim_band, dim_merchant, dim_card, rejected_count


def validate_data_quality(fact: pd.DataFrame, dim_time: pd.DataFrame, dim_band: pd.DataFrame,
                          dim_merchant: pd.DataFrame, dim_card: pd.DataFrame, initial_count: int, rejected_count: int):
    """Run rigorous sanity and integrity checks before warehouse loading."""
    print(f"[{datetime.datetime.now().isoformat()}] VALIDATION: Running data quality assertions...")

    # Check 1: Row count conservation
    if len(fact) != (initial_count - rejected_count):
        raise DataQualityError(f"Row count mismatch: {len(fact)} != {initial_count} - {rejected_count}")

    # Check 2: Foreign Key integrity (no orphan records)
    if not fact["time_key"].isin(dim_time["time_key"]).all():
        raise DataQualityError("Foreign key integrity check failed on dim_time!")
    if not fact["band_key"].isin(dim_band["band_key"]).all():
        raise DataQualityError("Foreign key integrity check failed on dim_amount_band!")
    if not fact["merchant_key"].isin(dim_merchant["merchant_key"]).all():
        raise DataQualityError("Foreign key integrity check failed on dim_merchant!")
    if not fact["card_key"].isin(dim_card["card_key"]).all():
        raise DataQualityError("Foreign key integrity check failed on dim_card!")

    # Check 3: Fraud ratio sanity check
    fraud_count = int(fact["is_fraud"].sum())
    fraud_ratio = fraud_count / len(fact)
    if fraud_count <= 0 or not (0.0005 <= fraud_ratio <= 0.01):
        raise DataQualityError(f"Fraud ratio sanity violation: {fraud_ratio:.5f} ({fraud_count} fraud txns)")

    # Check 4: Amount values non-negative
    if (fact["amount"] < 0).any():
        raise DataQualityError("Negative amount values detected in fact table!")

    print(f"-> All Data Quality Checks Passed (Fraud count: {fraud_count:,}, Ratio: {fraud_ratio*100:.3f}%).")


def load(fact: pd.DataFrame, dim_time: pd.DataFrame, dim_band: pd.DataFrame,
         dim_merchant: pd.DataFrame, dim_card: pd.DataFrame):
    """Load dimensions and fact table idempotently into the warehouse."""
    print(f"[{datetime.datetime.now().isoformat()}] LOAD: Persisting to database warehouse...")
    
    with engine.begin() as conn:
        # Load dimensions
        dim_time.to_sql("dim_time", conn, if_exists="replace", index=False)
        dim_band.to_sql("dim_amount_band", conn, if_exists="replace", index=False)
        dim_merchant.to_sql("dim_merchant", conn, if_exists="replace", index=False)
        dim_card.to_sql("dim_card", conn, if_exists="replace", index=False)
        
        # Load fact table
        fact.to_sql("fact_transaction", conn, if_exists="replace", index=False, chunksize=25000)

        # Re-create indexes for fast OLAP
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fact_time ON fact_transaction(time_key);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fact_band ON fact_transaction(band_key);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fact_merchant ON fact_transaction(merchant_key);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fact_card ON fact_transaction(card_key);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_fact_fraud ON fact_transaction(is_fraud);"))

    print(f"-> Successfully loaded {len(fact):,} fact records into fact_transaction.")


def log_etl_run(status: str, rows_extracted: int, rows_loaded: int, rows_rejected: int,
               fraud_rows: int, duration_seconds: float, quality_passed: bool, notes: str):
    """Record execution metrics into etl_run_log table."""
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO etl_run_log 
            (run_timestamp, status, rows_extracted, rows_loaded, rows_rejected, fraud_rows, duration_seconds, data_quality_passed, notes)
            VALUES (:ts, :status, :ext, :load, :rej, :fraud, :dur, :dq, :notes)
        """), {
            "ts": datetime.datetime.now(),
            "status": status,
            "ext": rows_extracted,
            "load": rows_loaded,
            "rej": rows_rejected,
            "fraud": fraud_rows,
            "dur": round(duration_seconds, 2),
            "dq": 1 if quality_passed else 0,
            "notes": notes
        })


def run_etl():
    """Main ETL orchestration entry point."""
    start_time = time.time()
    init_db()

    rows_extracted = 0
    rows_loaded = 0
    rows_rejected = 0
    fraud_rows = 0

    try:
        raw_df = extract()
        rows_extracted = len(raw_df)

        fact, dim_time, dim_band, dim_merchant, dim_card, rows_rejected = transform(raw_df)
        fraud_rows = int(fact["is_fraud"].sum())

        validate_data_quality(fact, dim_time, dim_band, dim_merchant, dim_card, rows_extracted, rows_rejected)

        load(fact, dim_time, dim_band, dim_merchant, dim_card)
        rows_loaded = len(fact)

        duration = time.time() - start_time
        log_etl_run(
            status="SUCCESS",
            rows_extracted=rows_extracted,
            rows_loaded=rows_loaded,
            rows_rejected=rows_rejected,
            fraud_rows=fraud_rows,
            duration_seconds=duration,
            quality_passed=True,
            notes=f"Clean ETL run. Dimensions loaded: 4. Fact rows: {rows_loaded}."
        )
        print(f"[{datetime.datetime.now().isoformat()}] ETL COMPLETE in {duration:.2f}s! Status: SUCCESS.")
        return True

    except Exception as e:
        duration = time.time() - start_time
        log_etl_run(
            status="FAILED",
            rows_extracted=rows_extracted,
            rows_loaded=rows_loaded,
            rows_rejected=rows_rejected,
            fraud_rows=fraud_rows,
            duration_seconds=duration,
            quality_passed=False,
            notes=str(e)
        )
        print(f"[{datetime.datetime.now().isoformat()}] ETL FAILED after {duration:.2f}s: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    run_etl()
