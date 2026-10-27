"""
Smart Battery AI - Personalized ML Feature & Model Unit Tests
=============================================================
Tests chronological leak-free historical feature calculation, circular math,
cold-start handling, circular blending, model serialization, and prediction bounds.
"""

from datetime import datetime, timedelta
import os
import pytest
import numpy as np
import pandas as pd
import joblib

from ml.preprocessing import (
    decode_cyclical_hour,
    circular_distance_hours,
    circular_error_minutes,
    extract_safe_features,
)
from ml.personalized_features import (
    PERSONALIZED_HISTORICAL_FEATURE_COLUMNS,
    ALL_PERSONALIZED_FEATURE_COLUMNS,
    compute_historical_features_chronological,
    extract_all_personalized_features,
    circular_blend_predictions,
)


@pytest.fixture
def mini_session_df():
    """Generates a 2-user deterministic dataset for leakage and history verification."""
    data = []
    base_time = datetime(2026, 1, 1, 22, 0)
    # User 1: 5 sessions with distinct unplug hours
    u1_unplugs = [7.0, 8.0, 6.5, 9.0, 7.5]
    for i, unp in enumerate(u1_unplugs):
        data.append({
            "user_id": 1,
            "date": (base_time + timedelta(days=i)).strftime("%Y-%m-%d"),
            "charging_start_time": (base_time + timedelta(days=i)).isoformat(),
            "charging_start_hour": 22.0,
            "unplug_hour": unp,
            "start_battery_percent": 30.0 + i,
            "charger_type": "standard",
            "weekday": i % 7,
            "is_weekend": 1 if (i % 7) >= 5 else 0,
            "previous_day_usage_minutes": 250.0 + i * 10,
            "profile_type": "REGULAR_OVERNIGHT",
        })

    # User 2: 2 sessions
    for i, unp in enumerate([8.5, 8.0]):
        data.append({
            "user_id": 2,
            "date": (base_time + timedelta(days=i)).strftime("%Y-%m-%d"),
            "charging_start_time": (base_time + timedelta(days=i)).isoformat(),
            "charging_start_hour": 23.0,
            "unplug_hour": unp,
            "start_battery_percent": 40.0,
            "charger_type": "fast",
            "weekday": i % 7,
            "is_weekend": 0,
            "previous_day_usage_minutes": 300.0,
            "profile_type": "HEAVY_USER",
        })

    return pd.DataFrame(data)


def test_historical_feature_leakage_prevention(mini_session_df):
    """1. Test that for every row, historical features use ONLY earlier sessions."""
    hist_df1 = compute_historical_features_chronological(mini_session_df)

    # Modify future sessions (rows 3 and 4 of User 1) in a duplicate dataset
    modified_df = mini_session_df.copy()
    modified_df.loc[3, "unplug_hour"] = 2.0  # Radically change session 3
    modified_df.loc[4, "unplug_hour"] = 3.0  # Radically change session 4

    hist_df2 = compute_historical_features_chronological(modified_df)

    # Verification: Rows 0, 1, 2 of User 1 must be 100% IDENTICAL despite future modifications!
    for col in PERSONALIZED_HISTORICAL_FEATURE_COLUMNS:
        np.testing.assert_allclose(
            hist_df1.loc[0:2, col].values,
            hist_df2.loc[0:2, col].values,
            err_msg=f"Data leakage detected in column {col}! Future changes corrupted earlier rows.",
            rtol=1e-6,
            atol=1e-6,
        )


def test_circular_historical_mean():
    """2. Test circular historical mean calculation across midnight."""
    # User with sessions at 23.0 (23:00) and 1.0 (01:00)
    data = [
        {"user_id": 1, "charging_start_time": "2026-01-01T20:00:00", "charging_start_hour": 20.0, "unplug_hour": 23.0, "start_battery_percent": 30.0, "charger_type": "standard", "weekday": 0, "is_weekend": 0, "previous_day_usage_minutes": 300.0},
        {"user_id": 1, "charging_start_time": "2026-01-02T20:00:00", "charging_start_hour": 20.0, "unplug_hour": 1.0, "start_battery_percent": 30.0, "charger_type": "standard", "weekday": 1, "is_weekend": 0, "previous_day_usage_minutes": 300.0},
        {"user_id": 1, "charging_start_time": "2026-01-03T20:00:00", "charging_start_hour": 20.0, "unplug_hour": 7.0, "start_battery_percent": 30.0, "charger_type": "standard", "weekday": 2, "is_weekend": 0, "previous_day_usage_minutes": 300.0},
    ]
    df = pd.DataFrame(data)
    hist_df = compute_historical_features_chronological(df)

    # At row 2 (after sessions at 23.0 and 1.0):
    # Vector average of 23.0 and 1.0:
    # 23.0 -> sin(-pi/12), cos(pi/12)
    # 1.0  -> sin(pi/12),  cos(pi/12)
    # sum_sin = 0, sum_cos = 2*cos(pi/12) > 0
    # Mean hour is exactly 0.0 (Midnight), NOT 12.0 (Noon)!
    s = hist_df.loc[2, "user_hist_unplug_sin_mean"]
    c = hist_df.loc[2, "user_hist_unplug_cos_mean"]
    mean_hour = decode_cyclical_hour(s, c)
    assert pytest.approx(mean_hour, abs=1e-4) == 0.0 or pytest.approx(mean_hour, abs=1e-4) == 24.0


def test_recent_3_feature_behavior(mini_session_df):
    """3. Test recent_3 feature reflects only the last 3 completed sessions."""
    hist_df = compute_historical_features_chronological(mini_session_df)

    # User 1 at row 4 (5th session):
    # Prior completed sessions are indices 0, 1, 2, 3 with unplug hours: [7.0, 8.0, 6.5, 9.0]
    # recent_3 must strictly be calculated from indices 1, 2, 3: [8.0, 6.5, 9.0]
    u1_sub = mini_session_df.iloc[1:4]["unplug_hour"].values
    expected_angles = u1_sub * (2.0 * np.pi / 24.0)
    exp_sin = np.sum(np.sin(expected_angles))
    exp_cos = np.sum(np.cos(expected_angles))
    r = np.sqrt(exp_sin**2 + exp_cos**2)
    expected_hour = decode_cyclical_hour(exp_sin / r, exp_cos / r)

    actual_s3 = hist_df.loc[4, "recent_3_unplug_sin_mean"]
    actual_c3 = hist_df.loc[4, "recent_3_unplug_cos_mean"]
    actual_hour = decode_cyclical_hour(actual_s3, actual_c3)

    assert pytest.approx(actual_hour, abs=1e-4) == expected_hour


def test_recent_7_feature_behavior():
    """4. Test recent_7 feature behaves correctly when history >= 7."""
    data = []
    base_time = datetime(2026, 1, 1, 10, 0)
    # 10 sessions with unplug hours 1.0, 2.0, ... 10.0
    for i in range(10):
        data.append({
            "user_id": 1,
            "charging_start_time": (base_time + timedelta(days=i)).isoformat(),
            "charging_start_hour": 10.0,
            "unplug_hour": float(i + 1),
            "start_battery_percent": 50.0,
            "charger_type": "standard",
            "weekday": i % 7,
            "is_weekend": 0,
            "previous_day_usage_minutes": 300.0,
        })
    df = pd.DataFrame(data)
    hist_df = compute_historical_features_chronological(df)

    # Row 8 (9th session): prior history is 0..7 (hours 1..8).
    # recent_7 covers the last 7 prior sessions: indices 1..7 (hours 2, 3, 4, 5, 6, 7, 8).
    recent_hours = np.array([2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    ang = recent_hours * (2.0 * np.pi / 24.0)
    s = np.sum(np.sin(ang))
    c = np.sum(np.cos(ang))
    exp_hour = decode_cyclical_hour(s, c)

    actual_hour = decode_cyclical_hour(hist_df.loc[8, "recent_7_unplug_sin_mean"], hist_df.loc[8, "recent_7_unplug_cos_mean"])
    assert pytest.approx(actual_hour, abs=1e-4) == exp_hour


def test_user_with_zero_history(mini_session_df):
    """5. Test cold-start behavior for user with 0 history."""
    hist_df = compute_historical_features_chronological(mini_session_df)

    # Check row 0 for User 1 and User 2
    for row_idx in [0, 5]:
        assert hist_df.loc[row_idx, "completed_history_count"] == 0.0
        # No NaNs or infs allowed
        assert not hist_df.loc[row_idx].isna().any()
        assert not np.isinf(hist_df.loc[row_idx]).any()
        # Default cold-start standard deviation
        assert hist_df.loc[row_idx, "user_hist_unplug_circular_std"] > 0.0


def test_user_with_one_history_record(mini_session_df):
    """6. Test history behavior for user with exactly 1 history record."""
    hist_df = compute_historical_features_chronological(mini_session_df)

    # Row 1 for User 1: exactly 1 prior session (unplug_hour = 7.0)
    assert hist_df.loc[1, "completed_history_count"] == 1.0
    hour_hist = decode_cyclical_hour(
        hist_df.loc[1, "user_hist_unplug_sin_mean"],
        hist_df.loc[1, "user_hist_unplug_cos_mean"]
    )
    assert pytest.approx(hour_hist, abs=1e-4) == 7.0

    # recent_3 and recent_7 must also equal this single session
    hour_r3 = decode_cyclical_hour(hist_df.loc[1, "recent_3_unplug_sin_mean"], hist_df.loc[1, "recent_3_unplug_cos_mean"])
    hour_r7 = decode_cyclical_hour(hist_df.loc[1, "recent_7_unplug_sin_mean"], hist_df.loc[1, "recent_7_unplug_cos_mean"])
    assert pytest.approx(hour_r3, abs=1e-4) == 7.0
    assert pytest.approx(hour_r7, abs=1e-4) == 7.0


def test_cold_start_fallback_blending():
    """7. Test circular blending fallback weights."""
    g_hour = 8.0
    p_hour = 10.0

    # 0 history -> 100% global prediction (8.0)
    b0 = circular_blend_predictions(g_hour, p_hour, history_counts=0, threshold=7.0)
    assert pytest.approx(b0, abs=1e-5) == 8.0

    # 7+ history -> 100% personalized prediction (10.0)
    b7 = circular_blend_predictions(g_hour, p_hour, history_counts=7, threshold=7.0)
    assert pytest.approx(b7, abs=1e-5) == 10.0

    b10 = circular_blend_predictions(g_hour, p_hour, history_counts=15, threshold=7.0)
    assert pytest.approx(b10, abs=1e-5) == 10.0


def test_circular_prediction_blending_midnight():
    """8. Test circular prediction blending across midnight (23:30 and 00:30 blended equally = 00:00)."""
    # 23:30 (23.5) and 00:30 (0.5)
    # Equal 50/50 blend (w = 0.5)
    blended = circular_blend_predictions(23.5, 0.5, history_counts=3.5, threshold=7.0)

    # Must produce 00:00 (0.0 or 24.0), strictly NOT 12.0 (Noon)!
    assert pytest.approx(blended, abs=1e-4) == 0.0 or pytest.approx(blended, abs=1e-4) == 24.0
    assert abs(blended - 12.0) > 10.0


def test_serialized_personalized_model_load():
    """9. Test loading serialized personalized models and metadata."""
    sin_path = "ml/models/personalized_unplug_sin_model.joblib"
    cos_path = "ml/models/personalized_unplug_cos_model.joblib"
    meta_path = "ml/models/personalized_model_metadata.json"

    assert os.path.exists(sin_path), "Missing personalized_unplug_sin_model.joblib"
    assert os.path.exists(cos_path), "Missing personalized_unplug_cos_model.joblib"
    assert os.path.exists(meta_path), "Missing personalized_model_metadata.json"

    m_sin = joblib.load(sin_path)
    m_cos = joblib.load(cos_path)

    # Generate dummy input matching ALL_PERSONALIZED_FEATURE_COLUMNS
    X_dummy = pd.DataFrame(np.zeros((2, len(ALL_PERSONALIZED_FEATURE_COLUMNS))), columns=ALL_PERSONALIZED_FEATURE_COLUMNS)
    X_dummy["start_hour_cos"] = 1.0
    X_dummy["user_hist_unplug_cos_mean"] = 1.0

    preds_sin = m_sin.predict(X_dummy)
    preds_cos = m_cos.predict(X_dummy)

    assert len(preds_sin) == 2
    assert len(preds_cos) == 2


def test_prediction_remains_between_0_and_24():
    """10. Test that predictions and circular blends always remain strictly in [0.0, 24.0)."""
    np.random.seed(42)
    g_hours = np.random.uniform(0.0, 24.0, size=100)
    p_hours = np.random.uniform(0.0, 24.0, size=100)
    counts = np.random.uniform(0, 50, size=100)

    blended = circular_blend_predictions(g_hours, p_hours, counts, threshold=7.0)

    assert np.all(blended >= 0.0)
    assert np.all(blended < 24.0)
