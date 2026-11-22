"""End-to-end integration and smoke tests for API endpoints."""
import pytest
from backend.main import health_check
from backend.routes.kpis import get_kpis
from backend.routes.olap import run_olap, export_olap_csv
from backend.routes.models import get_model_benchmarks, get_clustering_analysis
from backend.routes.predict import score_transaction, get_sample_transaction, TransactionInput
from backend.routes.review import submit_review, get_reviews, ReviewAction
from backend.routes.warehouse import preview_table

def test_e2e_health_check():
    data = health_check()
    assert data["status"] in ["HEALTHY", "DEGRADED"]
    assert data["database_connected"] is True
    assert data["deployed_model"] != "None"

def test_e2e_kpis_endpoint():
    data = get_kpis()
    assert "kpis" in data
    assert data["kpis"]["total_transactions"] > 280000
    assert data["kpis"]["fraud_transactions"] > 0
    assert len(data["by_period"]) == 4
    assert len(data["by_hour"]) == 24

def test_e2e_olap_endpoint():
    data = run_olap(group="merchant", period="Night")
    assert data["group_by"] == "merchant"
    assert data["group_label"] == "Merchant Category"
    assert len(data["data"]) > 0
    for row in data["data"]:
        assert "label" in row
        assert "total_txns" in row
        assert "fraud_rate_pct" in row

def test_e2e_olap_csv_export():
    res = export_olap_csv(group="period")
    assert res.media_type == "text/csv"
    assert "Content-Disposition" in res.headers

def test_e2e_models_endpoint():
    data = get_model_benchmarks()
    assert len(data["models"]) >= 3
    model_names = [m["name"] for m in data["models"]]
    assert "Isolation Forest" in model_names
    assert "Random Forest" in model_names
    assert "XGBoost" in model_names
    assert len(data["threshold_curve"]) > 0

def test_e2e_clustering_endpoint():
    data = get_clustering_analysis()
    assert data["cluster_count"] == 4
    assert len(data["clusters"]) == 4
    for c in data["clusters"]:
        assert "cluster_id" in c
        assert "fraud_rate_pct" in c
        assert "risk_index" in c

def test_e2e_predict_endpoint():
    payload = TransactionInput(amount=250.0, threshold=0.50, V1=0.5, V14=-4.2)
    data = score_transaction(payload)
    assert "probability" in data
    assert "prediction_label" in data
    assert len(data["top_shap_features"]) > 0

def test_e2e_sample_endpoint():
    legit_sample = get_sample_transaction(cls=0)
    assert legit_sample["actual_class"] == 0
    assert "amount" in legit_sample
    assert "V14" in legit_sample

    fraud_sample = get_sample_transaction(cls=1)
    assert fraud_sample["actual_class"] == 1

def test_e2e_review_submission_and_retrieval():
    payload = ReviewAction(
        txn_id=999999,
        amount=420.50,
        probability=0.88,
        decision="CONFIRMED_FRAUD",
        reviewer="SmokeTestAnalyst",
        notes="Automated E2E review verification test"
    )
    post_res = submit_review(payload)
    assert post_res["status"] == "SUCCESS"

    get_res = get_reviews()
    reviews = get_res["reviews"]
    assert any(r["txn_id"] == 999999 for r in reviews)

def test_e2e_warehouse_table_preview():
    data = preview_table(table="dim_time", limit=5)
    assert data["table"] == "dim_time"
    assert data["preview_count"] == 5
    assert "period" in data["columns"]
