"""Tests for OLAP aggregation queries, parameterization, and dimension whitelisting."""
import pytest
from backend.routes.olap import build_olap_query, GROUPS

def test_olap_whitelist_enforcement():
    # If a malicious or invalid group by column is supplied, it must default to 'period'
    sql, params, label = build_olap_query(group="malicious_col; DROP TABLE fact_transaction; --")
    assert "t.period" in sql
    assert label == "Time Period"
    assert "DROP TABLE" not in sql

def test_olap_parameterization():
    sql, params, label = build_olap_query(
        group="merchant",
        merchant="Grocery",
        card="Visa Debit",
        day=1,
        period="Morning"
    )
    assert "m.category = :merchant" in sql
    assert "c.card_type = :card" in sql
    assert "t.day = :day" in sql
    assert "t.period = :period" in sql
    assert params["merchant"] == "Grocery"
    assert params["card"] == "Visa Debit"
    assert params["day"] == 1
    assert params["period"] == "Morning"
