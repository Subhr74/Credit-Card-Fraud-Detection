"""Tests for Prediction endpoint, SHAP explainability, and sample loading."""
import pytest
from backend.ml_service import predict_transaction

def test_predict_scoring_and_shap_structure():
    sample_txn = {"amount": 250.0, "V1": -2.3, "V4": 3.1, "V10": -4.2, "V14": -5.6}
    result = predict_transaction(sample_txn, threshold=0.50)

    assert "probability" in result
    assert "is_fraud_predicted" in result
    assert "risk_tier" in result
    assert "top_shap_features" in result
    assert 0.0 <= result["probability"] <= 1.0

    # Ensure SHAP top features contains attributions
    assert len(result["top_shap_features"]) > 0
    top_feat = result["top_shap_features"][0]
    assert "feature" in top_feat
    assert "contribution" in top_feat
    assert top_feat["direction"] in ["RISK_INCREASING", "RISK_DECREASING"]

def test_predict_custom_threshold_tuning():
    sample_txn = {"amount": 50.0, "V14": -2.0}
    # Low threshold should flag more easily
    res_low = predict_transaction(sample_txn, threshold=0.01)
    res_high = predict_transaction(sample_txn, threshold=0.99)

    assert res_low["threshold"] == 0.01
    assert res_high["threshold"] == 0.99
    # If probability is between 0.01 and 0.99, low is flagged while high is not
    if 0.01 <= res_low["probability"] < 0.99:
        assert res_low["is_fraud_predicted"] is True
        assert res_high["is_fraud_predicted"] is False
