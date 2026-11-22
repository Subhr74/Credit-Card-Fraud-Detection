"""Unit tests for ETL pipeline, data quality assertions, and idempotency."""
import pytest
import pandas as pd
import numpy as np
from etl.etl import transform, validate_data_quality, DataQualityError, MERCHANTS, CARDS, AMOUNT_BANDS

def test_etl_transform_and_dimensions():
    # Create sample synthetic dataframe matching creditcard.csv schema
    sample_data = {
        "Time": [0.0, 3600.0, 7200.0, 10800.0, 0.0],  # 1 duplicate row
        "Amount": [5.0, 25.0, 150.0, 1500.0, 5.0],
        "Class": [0, 0, 1, 0, 0]
    }
    for i in range(1, 29):
        sample_data[f"V{i}"] = [0.1 * i] * 5

    df = pd.DataFrame(sample_data)
    fact, dim_time, dim_band, dim_merchant, dim_card, rejected = transform(df)

    # 1 duplicate row removed
    assert rejected == 1
    assert len(fact) == 4

    # Dimension integrity
    assert set(dim_band["band_key"]) == {1, 2, 3, 4, 5}
    assert len(dim_merchant) == len(MERCHANTS)
    assert len(dim_card) == len(CARDS)

    # Fact foreign key checks
    assert fact["time_key"].isin(dim_time["time_key"]).all()
    assert fact["band_key"].isin(dim_band["band_key"]).all()
    assert fact["merchant_key"].isin(dim_merchant["merchant_key"]).all()
    assert fact["card_key"].isin(dim_card["card_key"]).all()

def test_data_quality_assertion_failure_on_corrupt_data():
    sample_data = {
        "Time": [0.0, 3600.0],
        "Amount": [5.0, 25.0],
        "Class": [0, 0]  # Zero fraud cases -> should trigger sanity failure
    }
    for i in range(1, 29):
        sample_data[f"V{i}"] = [0.1 * i] * 2

    df = pd.DataFrame(sample_data)
    fact, dim_time, dim_band, dim_merchant, dim_card, rejected = transform(df)

    with pytest.raises(DataQualityError):
        validate_data_quality(fact, dim_time, dim_band, dim_merchant, dim_card, len(df), rejected)
