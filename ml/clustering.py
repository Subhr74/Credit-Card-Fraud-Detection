"""Unsupervised Data Mining: K-Means Transaction Clustering.

Groups transactions into behavioral clusters based on spending amount, time,
and primary variance components (V10, V12, V14, V17). Computes cluster fraud
concentration and risk profiles.
"""

import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.database import engine
from backend.config import RANDOM_SEED


def run_clustering(n_clusters: int = 4):
    """Run K-Means clustering on transaction profiles."""
    print("Fetching warehouse fact table for clustering...")
    with engine.connect() as conn:
        df = pd.read_sql("SELECT txn_id, amount, time_key, V10, V12, V14, V17, is_fraud FROM fact_transaction", conn)

    features = ["amount", "time_key", "V10", "V12", "V14", "V17"]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df[features])

    print(f"Fitting K-Means with K={n_clusters}...")
    kmeans = KMeans(n_clusters=n_clusters, random_state=RANDOM_SEED, n_init=10)
    clusters = kmeans.fit_predict(X_scaled)
    df["cluster"] = clusters

    cluster_profiles = []
    total_txns = len(df)
    total_fraud = int(df["is_fraud"].sum())

    cluster_names = [
        "Routine Daytime Micro-transactions",
        "High-Variance / Anomaly Profile",
        "Moderate Evening Commerce",
        "High-Value Commercial Spending"
    ]

    for c in range(n_clusters):
        c_df = df[df["cluster"] == c]
        c_count = len(c_df)
        c_fraud = int(c_df["is_fraud"].sum())
        fraud_rate = round(100.0 * c_fraud / c_count, 3) if c_count > 0 else 0.0
        avg_amount = round(float(c_df["amount"].mean()), 2)
        
        cluster_profiles.append({
            "cluster_id": c,
            "name": cluster_names[c] if c < len(cluster_names) else f"Cluster {c}",
            "txn_count": c_count,
            "txn_share_pct": round(100.0 * c_count / total_txns, 2),
            "fraud_count": c_fraud,
            "fraud_rate_pct": fraud_rate,
            "avg_amount": avg_amount,
            "mean_v14": round(float(c_df["V14"].mean()), 4),
            "mean_v10": round(float(c_df["V10"].mean()), 4),
            "risk_index": round(fraud_rate / (100.0 * total_fraud / total_txns), 2) if total_fraud > 0 else 1.0
        })

    cluster_profiles.sort(key=lambda x: -x["fraud_rate_pct"])
    return cluster_profiles


if __name__ == "__main__":
    run_clustering()
