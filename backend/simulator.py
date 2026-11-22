"""High-Performance Real-Time Transaction Stream Simulator.

Streams held-out transactions at high speed with instant index lookups,
evaluates risk via ML scoring, flags suspicious events, and broadcasts via SSE.
"""

import time
import asyncio
import random
import datetime
from typing import List, Dict, Any
from backend.database import execute_query
from backend.ml_service import predict_transaction

class TransactionSimulator:
    def __init__(self):
        self.is_running: bool = False
        self.interval_seconds: float = 1.0
        self.stream_history: List[Dict[str, Any]] = []
        self.alerts_feed: List[Dict[str, Any]] = []
        self.max_history: int = 100
        self.max_alerts: int = 50
        self._subscribers: List[asyncio.Queue] = []
        self._task: asyncio.Task = None
        self.total_streamed: int = 0
        self.total_alerts: int = 0
        self.fraud_ids: List[int] = []
        self.max_txn_id: int = 283726
        self._init_ids()

    def _init_ids(self):
        """Pre-cache fraud IDs for sub-millisecond random sampling without full table scans."""
        try:
            rows = execute_query("SELECT txn_id FROM fact_transaction WHERE is_fraud = 1")
            self.fraud_ids = [r["txn_id"] for r in rows] if rows else []
            count_row = execute_query("SELECT MAX(txn_id) as max_id FROM fact_transaction")
            if count_row and count_row[0]["max_id"]:
                self.max_txn_id = count_row[0]["max_id"]
        except Exception:
            pass

    def start(self, interval: float = 1.0):
        if not self.is_running:
            self.is_running = True
            self.interval_seconds = interval
            try:
                loop = asyncio.get_running_loop()
                self._task = loop.create_task(self.run_loop())
            except RuntimeError:
                pass
            print(f"[SIMULATOR] Real-time stream running at {self.interval_seconds}s interval.")

    def stop(self):
        if self.is_running:
            self.is_running = False
            if self._task:
                self._task.cancel()
                self._task = None
            print("[SIMULATOR] Stream stopped.")

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "total_streamed": self.total_streamed,
            "total_alerts": self.total_alerts,
            "active_subscribers": len(self._subscribers),
        }

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def broadcast(self, event_data: dict):
        dead_queues = []
        for q in self._subscribers:
            try:
                q.put_nowait(event_data)
            except Exception:
                dead_queues.append(q)
        for q in dead_queues:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def fetch_sample_transaction(self) -> dict:
        """Fast indexed fetch: ~18% chance of picking a known fraud incident to ensure rich live demo."""
        if not self.fraud_ids:
            self._init_ids()

        is_fraud = random.random() < 0.18
        if is_fraud and self.fraud_ids:
            target_id = random.choice(self.fraud_ids)
        else:
            target_id = random.randint(1, max(1, self.max_txn_id))

        sql = """
        SELECT f.*, m.category as merchant, c.card_type as card, t.period
        FROM fact_transaction f
        LEFT JOIN dim_merchant m ON f.merchant_key = m.merchant_key
        LEFT JOIN dim_card c ON f.card_key = c.card_key
        LEFT JOIN dim_time t ON f.time_key = t.time_key
        WHERE f.txn_id = :id
        LIMIT 1
        """
        rows = execute_query(sql, {"id": target_id})
        return rows[0] if rows else {}

    async def step(self):
        """Score one transaction event and broadcast in real time."""
        raw_txn = self.fetch_sample_transaction()
        if not raw_txn:
            return None

        # Score with champion ML model
        result = predict_transaction(raw_txn, threshold=0.50)

        event = {
            "txn_id": raw_txn.get("txn_id", random.randint(100000, 999999)),
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
            "amount": float(raw_txn.get("amount", 0.0)),
            "merchant": raw_txn.get("merchant", "Online Commerce"),
            "card": raw_txn.get("card", "Credit Card"),
            "period": raw_txn.get("period", "Day"),
            "probability": result["probability"],
            "prediction": result["prediction_label"],
            "risk_tier": result["risk_tier"],
            "is_actual_fraud": int(raw_txn.get("is_fraud", 0)),
            "top_shap_features": result["top_shap_features"][:4],
        }

        self.total_streamed += 1
        self.stream_history.insert(0, event)
        if len(self.stream_history) > self.max_history:
            self.stream_history.pop()

        # Flag high-risk transactions
        if result["is_fraud_predicted"] or result["probability"] >= 0.50:
            self.total_alerts += 1
            alert_entry = {
                "alert_id": f"ALT-{self.total_alerts:04d}",
                "txn_id": event["txn_id"],
                "timestamp": event["timestamp"],
                "amount": event["amount"],
                "merchant": event["merchant"],
                "card": event["card"],
                "probability": event["probability"],
                "risk_tier": event["risk_tier"],
                "top_features": result["top_shap_features"][:3],
                "reviewed": False
            }
            self.alerts_feed.insert(0, alert_entry)
            if len(self.alerts_feed) > self.max_alerts:
                self.alerts_feed.pop()

        await self.broadcast(event)
        return event

    async def run_loop(self):
        while self.is_running:
            try:
                await self.step()
            except Exception as e:
                print(f"[SIMULATOR ERROR] {e}")
            await asyncio.sleep(self.interval_seconds)

simulator = TransactionSimulator()
