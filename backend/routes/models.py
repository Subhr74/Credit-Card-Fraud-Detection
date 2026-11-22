"""Model comparison, Registry, and Clustering Router."""
from fastapi import APIRouter
from backend.ml_service import get_results
from backend.database import execute_query

router = APIRouter(prefix="/api", tags=["Models & Mining"])

@router.get("/models")
def get_model_benchmarks():
    """Retrieve performance metrics, threshold curve, and confusion matrices for all evaluated models."""
    results = get_results()
    
    # Query database model registry for live deployed status
    registry_rows = execute_query("SELECT * FROM model_registry ORDER BY model_id DESC")

    return {
        "models": results.get("models", []),
        "best_model": results.get("best", "Random Forest"),
        "headline_metric_explanation": results.get("headline_metric_explanation", ""),
        "feature_importance": results.get("importance", []),
        "threshold_curve": results.get("threshold_curve", []),
        "registry": registry_rows,
        "trained_at": results.get("trained_at", "")
    }

@router.get("/clustering")
def get_clustering_analysis():
    """Retrieve K-Means transaction cluster profiles and fraud concentration risk indices."""
    results = get_results()
    clusters = results.get("clustering", [])
    return {
        "technique": "K-Means Clustering (Unsupervised Anomaly Discovery)",
        "feature_space": ["amount", "time_key", "V10", "V12", "V14", "V17"],
        "cluster_count": len(clusters),
        "clusters": clusters
    }
