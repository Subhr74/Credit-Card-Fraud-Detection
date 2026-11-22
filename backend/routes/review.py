"""Analyst Review Queue Router."""
import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.database import execute_query

router = APIRouter(prefix="/api", tags=["Analyst Review"])

class ReviewAction(BaseModel):
    txn_id: int = Field(..., description="Transaction ID being reviewed")
    amount: float = Field(..., description="Transaction amount")
    probability: float = Field(..., description="Predicted fraud probability")
    decision: str = Field(..., description="'CONFIRMED_FRAUD' or 'FALSE_ALARM'")
    reviewer: str = Field("Risk Analyst", description="Name/username of analyst")
    notes: Optional[str] = Field("", description="Resolution rationale or notes")

@router.post("/review")
def submit_review(payload: ReviewAction):
    """Store analyst investigation outcome in the database."""
    if payload.decision not in ["CONFIRMED_FRAUD", "FALSE_ALARM"]:
        raise HTTPException(status_code=400, detail="Decision must be 'CONFIRMED_FRAUD' or 'FALSE_ALARM'")

    sql = """
    INSERT INTO analyst_reviews (txn_id, amount, probability, decision, reviewer, notes, reviewed_at)
    VALUES (:txn_id, :amount, :prob, :decision, :reviewer, :notes, :ts)
    """
    execute_query(sql, {
        "txn_id": payload.txn_id,
        "amount": payload.amount,
        "prob": payload.probability,
        "decision": payload.decision,
        "reviewer": payload.reviewer,
        "notes": payload.notes or "Standard investigation completed.",
        "ts": datetime.datetime.now()
    })
    return {"status": "SUCCESS", "message": f"Transaction #{payload.txn_id} marked as {payload.decision}"}

@router.get("/reviews")
def get_reviews():
    """Retrieve historical analyst dispositions."""
    sql = "SELECT * FROM analyst_reviews ORDER BY review_id DESC LIMIT 50"
    rows = execute_query(sql)
    return {"reviews": rows, "count": len(rows)}

@router.get("/reviews/pending")
def get_pending_review_candidates():
    """Retrieve high-risk transactions from warehouse or simulation awaiting review."""
    sql = """
    SELECT f.txn_id, f.amount, f.is_fraud, m.category as merchant, c.card_type as card, t.period
    FROM fact_transaction f
    JOIN dim_merchant m ON f.merchant_key = m.merchant_key
    JOIN dim_card c ON f.card_key = c.card_key
    JOIN dim_time t ON f.time_key = t.time_key
    WHERE f.is_fraud = 1 OR f.amount > 500
    ORDER BY RANDOM()
    LIMIT 10
    """
    rows = execute_query(sql)
    return {"pending_queue": rows}
