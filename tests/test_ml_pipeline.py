import os
import tempfile
import pytest

# Skip ML tests if ML packages are not yet installed
pytest.importorskip("pandas")
pytest.importorskip("numpy")
pytest.importorskip("sklearn")

from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from ml.feature_engineering import extract_features_from_timestamp
from ml.model import (
    UnplugPredictor,
    CircularTargetRegressor,
    save_circular_model,
    load_circular_model,
)
from ml.preprocessing import (
    SAFE_FEATURE_COLUMNS,
    EXCLUDED_LEAKAGE_COLUMNS,
    encode_cyclical_hour,
    decode_cyclical_hour,
    circular_distance_hours,
    circular_error_minutes,
    extract_safe_features,
    chronological_per_user_split,
)


def test_feature_extraction():
    """Legacy feature extraction compatibility check."""
    test_dt = datetime(2026, 9, 10, 23, 30, tzinfo=timezone.utc)
    features = extract_features_from_timestamp(test_dt, start_battery_pct=35.0)

    assert "sin_hour" in features.columns
    assert "cos_hour" in features.columns
    assert "day_of_week" in features.columns
    assert "is_weekend" in features.columns
    assert "start_battery_pct" in features.columns

    # Check bounds
    assert -1.0 <= features["sin_hour"].iloc[0] <= 1.0
    assert -1.0 <= features["cos_hour"].iloc[0] <= 1.0
    assert features["start_battery_pct"].iloc[0] == 35.0


def test_unplug_predictor_fallback():
    """Verify fallback to heuristic rules when no trained model is loaded."""
    predictor = UnplugPredictor(model_path="non_existent.joblib")
    assert not predictor.is_loaded()

    night_time = datetime(2026, 9, 10, 22, 0, tzinfo=timezone.utc)
    predicted_unplug, confidence = predictor.predict("user_123", night_time)

    assert predicted_unplug > night_time
    assert confidence > 0.5


def test_cyclical_hour_encoding():
    """1. Test cyclical hour encoding at key quadrant anchors."""
    # 00:00 (angle 0) -> sin=0, cos=1
    s0, c0 = encode_cyclical_hour(0.0)
    assert pytest.approx(s0, abs=1e-6) == 0.0
    assert pytest.approx(c0, abs=1e-6) == 1.0

    # 06:00 (angle pi/2) -> sin=1, cos=0
    s6, c6 = encode_cyclical_hour(6.0)
    assert pytest.approx(s6, abs=1e-6) == 1.0
    assert pytest.approx(c6, abs=1e-6) == 0.0

    # 12:00 (angle pi) -> sin=0, cos=-1
    s12, c12 = encode_cyclical_hour(12.0)
    assert pytest.approx(s12, abs=1e-6) == 0.0
    assert pytest.approx(c12, abs=1e-6) == -1.0

    # 18:00 (angle 3pi/2) -> sin=-1, cos=0
    s18, c18 = encode_cyclical_hour(18.0)
    assert pytest.approx(s18, abs=1e-6) == -1.0
    assert pytest.approx(c18, abs=1e-6) == 0.0


def test_cyclical_hour_decoding():
    """2. Test cyclical hour decoding and roundtrip fidelity."""
    # Known anchors
    assert pytest.approx(decode_cyclical_hour(0.0, 1.0), abs=1e-5) == 0.0
    assert pytest.approx(decode_cyclical_hour(1.0, 0.0), abs=1e-5) == 6.0
    assert pytest.approx(decode_cyclical_hour(0.0, -1.0), abs=1e-5) == 12.0
    assert pytest.approx(decode_cyclical_hour(-1.0, 0.0), abs=1e-5) == 18.0

    # Roundtrip check across 48 fractional test hours
    test_hours = np.linspace(0.0, 23.75, 48)
    sin_vals, cos_vals = encode_cyclical_hour(test_hours)
    decoded_hours = decode_cyclical_hour(sin_vals, cos_vals)
    np.testing.assert_allclose(test_hours, decoded_hours, atol=1e-5)


def test_midnight_error_calculation():
    """3. Test circular distance and error across midnight."""
    # 23.5 (23:30) vs 0.5 (00:30) -> 1.0 hour distance (60 minutes)
    dist1 = circular_distance_hours(23.5, 0.5)
    err1 = circular_error_minutes(23.5, 0.5)
    assert pytest.approx(dist1, abs=1e-5) == 1.0
    assert pytest.approx(err1, abs=1e-5) == 60.0

    # Commutative property: 0.5 vs 23.5
    dist2 = circular_distance_hours(0.5, 23.5)
    assert pytest.approx(dist2, abs=1e-5) == 1.0

    # 23.8 vs 0.2 -> 0.4 hours (24 minutes)
    dist3 = circular_distance_hours(23.8, 0.2)
    err3 = circular_error_minutes(23.8, 0.2)
    assert pytest.approx(dist3, abs=1e-5) == 0.4
    assert pytest.approx(err3, abs=1e-5) == 24.0

    # Same time -> 0 error
    assert pytest.approx(circular_error_minutes(7.5, 7.5), abs=1e-5) == 0.0


def test_preprocessing_safe_features():
    """4. Test preprocessing extracts only safe features and excludes leakage."""
    sample_data = pd.DataFrame([{
        "session_id": "sess_001",
        "user_id": 1,
        "date": "2026-01-15",
        "charging_start_time": "2026-01-15T22:30:00",
        "charging_start_hour": 22.5,
        "unplug_time": "2026-01-16T07:15:00",
        "unplug_hour": 7.25,
        "start_battery_percent": 32.0,
        "end_battery_percent": 95.0,            # Leaking
        "average_temperature": 31.5,            # Leaking
        "charging_duration_minutes": 525.0,     # Leaking
        "charger_type": "standard",
        "screen_usage_minutes": 320.0,          # Leaking
        "weekday": 3,
        "is_weekend": 0,
        "previous_day_usage_minutes": 280.0,
        "profile_type": "REGULAR_OVERNIGHT",    # Simulation only
    }])

    X = extract_safe_features(sample_data)

    # All safe columns present
    for col in SAFE_FEATURE_COLUMNS:
        assert col in X.columns

    # No leakage columns present
    for leak_col in EXCLUDED_LEAKAGE_COLUMNS:
        assert leak_col not in X.columns

    # Exact expected feature count
    assert len(X.columns) == len(SAFE_FEATURE_COLUMNS)
    assert X["start_battery_percent"].iloc[0] == 32.0
    assert X["charger_type_standard"].iloc[0] == 1.0
    assert X["charger_type_fast"].iloc[0] == 0.0


def test_chronological_split():
    """5. Test chronological per-user split guarantees temporal precedence."""
    # Synthetic 2-user test DataFrame with timestamps
    data = []
    base_time = datetime(2026, 1, 1, 10, 0)
    for u in [1, 2]:
        for day in range(10):
            data.append({
                "user_id": u,
                "charging_start_time": (base_time + timedelta(days=day)).isoformat(),
                "charging_start_hour": 10.0,
                "unplug_hour": 18.0,
                "start_battery_percent": 40.0,
                "charger_type": "standard",
                "weekday": 0,
                "is_weekend": 0,
                "previous_day_usage_minutes": 300.0,
            })
    toy_df = pd.DataFrame(data)

    train_df, test_df = chronological_per_user_split(toy_df, train_ratio=0.8)

    # 10 sessions per user * 2 users = 20 total. 8 train, 2 test per user
    assert len(train_df) == 16
    assert len(test_df) == 4
    assert train_df["user_id"].nunique() == 2
    assert test_df["user_id"].nunique() == 2

    # Verify temporal ordering: For each user, max(train_time) < min(test_time)
    for u in [1, 2]:
        u_train = pd.to_datetime(train_df[train_df["user_id"] == u]["charging_start_time"])
        u_test = pd.to_datetime(test_df[test_df["user_id"] == u]["charging_start_time"])
        assert u_train.max() < u_test.min()


def test_prediction_output_bounds():
    """6. Test prediction output is always strictly within [0.0, 24.0)."""
    # Create extreme sin/cos pairs including outside [-1, 1] bounds
    np.random.seed(42)
    random_sin = np.random.uniform(-10.0, 10.0, size=200)
    random_cos = np.random.uniform(-10.0, 10.0, size=200)

    decoded = decode_cyclical_hour(random_sin, random_cos, period=24.0)

    assert np.all(decoded >= 0.0)
    assert np.all(decoded < 24.0)


def test_model_save_and_load():
    """7. Test dual circular model saving, loading, and prediction parity."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create dummy linear models
        X_dummy = pd.DataFrame({
            "f1": [1.0, 2.0, 3.0, 4.0],
            "f2": [0.5, 0.8, 0.2, 0.9],
        })
        y_sin = np.array([0.0, 1.0, 0.0, -1.0])
        y_cos = np.array([1.0, 0.0, -1.0, 0.0])

        m_sin = LinearRegression().fit(X_dummy, y_sin)
        m_cos = LinearRegression().fit(X_dummy, y_cos)
        metadata = {"model_name": "TestLinear", "test_metric": 42.0}

        save_circular_model(m_sin, m_cos, metadata, model_dir=tmp_dir)

        loaded_sin, loaded_cos, loaded_meta = load_circular_model(model_dir=tmp_dir)

        np.testing.assert_allclose(m_sin.predict(X_dummy), loaded_sin.predict(X_dummy))
        np.testing.assert_allclose(m_cos.predict(X_dummy), loaded_cos.predict(X_dummy))
        assert loaded_meta["model_name"] == "TestLinear"


def test_inference_single_record():
    """8. Test end-to-end inference on one charging session record."""
    predictor = UnplugPredictor(model_dir="ml/models")
    assert predictor.is_loaded()

    night_start = datetime(2026, 9, 10, 22, 15)
    pred_unplug, confidence = predictor.predict(
        user_id="user_test",
        plug_time=night_start,
        start_battery_pct=25.0,
        charger_type="fast",
        previous_day_usage_minutes=450.0,
    )

    # Predicted unplug must occur in the future
    assert pred_unplug > night_start
    # Difference should be plausible (e.g. between 1 hour and 16 hours)
    duration_hours = (pred_unplug - night_start).total_seconds() / 3600.0
    assert 1.0 <= duration_hours <= 16.0
    assert 0.60 <= confidence <= 1.0
