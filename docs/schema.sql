-- ============================================================================
-- Credit Card Fraud Detection Data Warehouse - Star Schema DDL
-- Compatible with PostgreSQL and SQLite
-- ============================================================================

-- 1. Dimension Tables
CREATE TABLE IF NOT EXISTS dim_time (
    time_key INTEGER PRIMARY KEY,           -- Hour index since start (0 - 47)
    day INTEGER NOT NULL,                   -- Day 1 or Day 2
    hour INTEGER NOT NULL,                  -- Hour of day (0 - 23)
    period VARCHAR(20) NOT NULL             -- Night (0-5), Morning (6-11), Afternoon (12-17), Evening (18-23)
);

CREATE TABLE IF NOT EXISTS dim_amount_band (
    band_key INTEGER PRIMARY KEY,           -- 1 to 5
    band_name VARCHAR(50) NOT NULL,         -- Micro, Low, Medium, High, Jumbo
    min_amount NUMERIC(10,2) NOT NULL,
    max_amount NUMERIC(10,2) NOT NULL
);

-- Note: Merchant category and card type are simulated dimensions generated with fixed seed (seed=42)
-- because the public Kaggle ULB dataset is strictly anonymised.
CREATE TABLE IF NOT EXISTS dim_merchant (
    merchant_key INTEGER PRIMARY KEY,
    category VARCHAR(50) NOT NULL,          -- Grocery, Electronics, Travel, Restaurants, etc. (SIMULATED)
    risk_level VARCHAR(20) NOT NULL         -- Low, Medium, High (SIMULATED)
);

CREATE TABLE IF NOT EXISTS dim_card (
    card_key INTEGER PRIMARY KEY,
    card_type VARCHAR(50) NOT NULL,         -- Visa Debit, Visa Credit, Mastercard, RuPay (SIMULATED)
    network VARCHAR(30) NOT NULL            -- Visa, Mastercard, RuPay, Amex (SIMULATED)
);

-- 2. Fact Table
CREATE TABLE IF NOT EXISTS fact_transaction (
    txn_id INTEGER PRIMARY KEY,
    time_key INTEGER NOT NULL REFERENCES dim_time(time_key),
    band_key INTEGER NOT NULL REFERENCES dim_amount_band(band_key),
    merchant_key INTEGER NOT NULL REFERENCES dim_merchant(merchant_key),
    card_key INTEGER NOT NULL REFERENCES dim_card(card_key),
    amount NUMERIC(12,2) NOT NULL,
    is_fraud INTEGER NOT NULL DEFAULT 0,
    -- Anonymised PCA features from Kaggle dataset
    V1 NUMERIC(10,6), V2 NUMERIC(10,6), V3 NUMERIC(10,6), V4 NUMERIC(10,6),
    V5 NUMERIC(10,6), V6 NUMERIC(10,6), V7 NUMERIC(10,6), V8 NUMERIC(10,6),
    V9 NUMERIC(10,6), V10 NUMERIC(10,6), V11 NUMERIC(10,6), V12 NUMERIC(10,6),
    V13 NUMERIC(10,6), V14 NUMERIC(10,6), V15 NUMERIC(10,6), V16 NUMERIC(10,6),
    V17 NUMERIC(10,6), V18 NUMERIC(10,6), V19 NUMERIC(10,6), V20 NUMERIC(10,6),
    V21 NUMERIC(10,6), V22 NUMERIC(10,6), V23 NUMERIC(10,6), V24 NUMERIC(10,6),
    V25 NUMERIC(10,6), V26 NUMERIC(10,6), V27 NUMERIC(10,6), V28 NUMERIC(10,6),
    predicted_probability NUMERIC(6,4),
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Fast OLAP Query Performance
CREATE INDEX IF NOT EXISTS ix_fact_time ON fact_transaction(time_key);
CREATE INDEX IF NOT EXISTS ix_fact_band ON fact_transaction(band_key);
CREATE INDEX IF NOT EXISTS ix_fact_merchant ON fact_transaction(merchant_key);
CREATE INDEX IF NOT EXISTS ix_fact_card ON fact_transaction(card_key);
CREATE INDEX IF NOT EXISTS ix_fact_fraud ON fact_transaction(is_fraud);
CREATE INDEX IF NOT EXISTS ix_fact_fraud_time ON fact_transaction(is_fraud, time_key);

-- 3. Operational & Governance Tables
CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL,
    rows_extracted INTEGER NOT NULL,
    rows_loaded INTEGER NOT NULL,
    rows_rejected INTEGER NOT NULL,
    fraud_rows INTEGER NOT NULL,
    duration_seconds NUMERIC(8,2) NOT NULL,
    data_quality_passed INTEGER NOT NULL DEFAULT 1,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS model_registry (
    model_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    version VARCHAR(30) NOT NULL,
    algorithm VARCHAR(50) NOT NULL,
    metrics TEXT NOT NULL,                  -- JSON string of metrics
    top_features TEXT,                      -- JSON list of top features
    is_active INTEGER NOT NULL DEFAULT 0,
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analyst_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_id INTEGER NOT NULL,
    amount NUMERIC(12,2),
    probability NUMERIC(6,4),
    decision VARCHAR(30) NOT NULL,          -- 'CONFIRMED_FRAUD', 'FALSE_ALARM'
    reviewer VARCHAR(50) NOT NULL,
    notes TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Aggregate Rollup View for OLAP Acceleration
CREATE VIEW IF NOT EXISTS v_fraud_by_period AS
SELECT 
    t.period,
    COUNT(*) AS total_txns,
    SUM(f.is_fraud) AS fraud_count,
    ROUND(100.0 * SUM(f.is_fraud) / COUNT(*), 4) AS fraud_rate_pct,
    ROUND(SUM(f.amount), 2) AS total_amount,
    ROUND(SUM(CASE WHEN f.is_fraud = 1 THEN f.amount ELSE 0 END), 2) AS amount_at_risk
FROM fact_transaction f
JOIN dim_time t ON f.time_key = t.time_key
GROUP BY t.period;

CREATE VIEW IF NOT EXISTS v_fraud_by_merchant AS
SELECT 
    m.category AS merchant_category,
    COUNT(*) AS total_txns,
    SUM(f.is_fraud) AS fraud_count,
    ROUND(100.0 * SUM(f.is_fraud) / COUNT(*), 4) AS fraud_rate_pct,
    ROUND(SUM(f.amount), 2) AS total_amount,
    ROUND(SUM(CASE WHEN f.is_fraud = 1 THEN f.amount ELSE 0 END), 2) AS amount_at_risk
FROM fact_transaction f
JOIN dim_merchant m ON f.merchant_key = m.merchant_key
GROUP BY m.category;
