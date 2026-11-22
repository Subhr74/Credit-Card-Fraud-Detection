"""Prediction and Transaction Screening Router."""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from backend.ml_service import predict_transaction
from backend.database import execute_query

router = APIRouter(prefix="/api", tags=["Predict & Screen"])

class TransactionInput(BaseModel):
    amount: float = Field(..., description="Transaction dollar amount (e.g. 149.50)")
    threshold: Optional[float] = Field(0.50, ge=0.01, le=0.99, description="Custom decision threshold (0.01 - 0.99)")
    # Optional PCA components V1 to V28
    V1: Optional[float] = 0.0
    V2: Optional[float] = 0.0
    V3: Optional[float] = 0.0
    V4: Optional[float] = 0.0
    V5: Optional[float] = 0.0
    V6: Optional[float] = 0.0
    V7: Optional[float] = 0.0
    V8: Optional[float] = 0.0
    V9: Optional[float] = 0.0
    V10: Optional[float] = 0.0
    V11: Optional[float] = 0.0
    V12: Optional[float] = 0.0
    V13: Optional[float] = 0.0
    V14: Optional[float] = 0.0
    V15: Optional[float] = 0.0
    V16: Optional[float] = 0.0
    V17: Optional[float] = 0.0
    V18: Optional[float] = 0.0
    V19: Optional[float] = 0.0
    V20: Optional[float] = 0.0
    V21: Optional[float] = 0.0
    V22: Optional[float] = 0.0
    V23: Optional[float] = 0.0
    V24: Optional[float] = 0.0
    V25: Optional[float] = 0.0
    V26: Optional[float] = 0.0
    V27: Optional[float] = 0.0
    V28: Optional[float] = 0.0

@router.post("/predict")
def score_transaction(payload: TransactionInput):
    """Score a transaction against the champion model with SHAP feature attributions."""
    data = payload.model_dump()
    threshold = data.pop("threshold", 0.50)
    result = predict_transaction(data, threshold=threshold)
    return result

@router.get("/sample")
def get_sample_transaction(cls: int = Query(0, description="0 = Legitimate, 1 = Fraud")):
    """Fetch an actual transaction record from the warehouse for testing."""
    sql = "SELECT * FROM fact_transaction WHERE is_fraud = :cls ORDER BY RANDOM() LIMIT 1"
    rows = execute_query(sql, {"cls": cls})
    if not rows:
        raise HTTPException(status_code=404, detail="No matching transaction found.")
    
    row = rows[0]
    # Filter features for form
    features = {f"V{i}": round(float(row.get(f"V{i}", 0.0)), 4) for i in range(1, 29)}
    features["amount"] = round(float(row.get("amount", 0.0)), 2)
    features["txn_id"] = row.get("txn_id")
    features["actual_class"] = row.get("is_fraud")
    return features
