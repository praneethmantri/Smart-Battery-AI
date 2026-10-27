import pytest
import pandas as pd
from datetime import datetime
from scripts.generate_synthetic_data import (
    generate_synthetic_users,
    generate_synthetic_charging_sessions,
    validate_dataset,
    run_quality_checks,
    PROFILES,
    CHARGER_TYPES,
)


@pytest.fixture(scope="module")
def generated_data():
    """Generates a reproducible test dataset using the generator."""
    users_df = generate_synthetic_users(num_users=100, seed=42)
    sessions_df = generate_synthetic_charging_sessions(users_df, num_days=60, seed=42)
    return users_df, sessions_df


def test_reproducibility():
    """Verify that generating with the same seed produces deterministic results."""
    users1 = generate_synthetic_users(num_users=10, seed=123)
    users2 = generate_synthetic_users(num_users=10, seed=123)
    pd.testing.assert_frame_equal(users1, users2)

    sess1 = generate_synthetic_charging_sessions(users1, num_days=5, seed=123)
    sess2 = generate_synthetic_charging_sessions(users2, num_days=5, seed=123)
    pd.testing.assert_frame_equal(sess1, sess2)


def test_required_columns(generated_data):
    """Verify presence of all mandatory columns in users and charging datasets."""
    users_df, sessions_df = generated_data

    expected_user_cols = {
        "user_id",
        "profile_type",
        "typical_weekday_charge_hour",
        "typical_weekday_unplug_hour",
        "typical_weekend_charge_hour",
        "typical_weekend_unplug_hour",
        "baseline_daily_screen_minutes",
        "preferred_charger_type",
    }
    assert expected_user_cols.issubset(set(users_df.columns))

    expected_session_cols = {
        "session_id",
        "user_id",
        "date",
        "charging_start_time",
        "unplug_time",
        "charging_start_hour",
        "unplug_hour",
        "start_battery_percent",
        "end_battery_percent",
        "average_temperature",
        "charging_duration_minutes",
        "charger_type",
        "screen_usage_minutes",
        "weekday",
        "is_weekend",
        "previous_day_usage_minutes",
        "profile_type",
    }
    assert expected_session_cols.issubset(set(sessions_df.columns))


def test_dataset_size(generated_data):
    """Verify at least 100 unique users and >= 6,000 charging sessions."""
    users_df, sessions_df = generated_data
    assert len(users_df) == 100
    assert sessions_df["user_id"].nunique() == 100
    assert len(sessions_df) >= 6000


def test_profile_categories(generated_data):
    """Verify all 6 behavioral profiles are represented in the population."""
    users_df, sessions_df = generated_data
    user_profiles = set(users_df["profile_type"].unique())
    session_profiles = set(sessions_df["profile_type"].unique())

    assert user_profiles == set(PROFILES)
    assert session_profiles == set(PROFILES)


def test_battery_percentage_validity(generated_data):
    """Verify all battery percentages are within 0-100 and end SOC > start SOC."""
    _, sessions_df = generated_data
    assert (sessions_df["start_battery_percent"] >= 0.0).all()
    assert (sessions_df["start_battery_percent"] <= 100.0).all()
    assert (sessions_df["end_battery_percent"] >= 0.0).all()
    assert (sessions_df["end_battery_percent"] <= 100.0).all()
    assert (sessions_df["end_battery_percent"] > sessions_df["start_battery_percent"]).all()


def test_positive_charging_durations(generated_data):
    """Verify that all charging session durations are strictly positive."""
    _, sessions_df = generated_data
    assert (sessions_df["charging_duration_minutes"] > 0.0).all()


def test_timestamp_consistency(generated_data):
    """Verify unplug timestamp is strictly after charging start timestamp."""
    _, sessions_df = generated_data
    start_dt = pd.to_datetime(sessions_df["charging_start_time"], format="ISO8601")
    unplug_dt = pd.to_datetime(sessions_df["unplug_time"], format="ISO8601")

    assert (unplug_dt > start_dt).all()


def test_validation_function_all_rules_pass(generated_data):
    """Ensure the automated 11-rule validation function returns 100% pass."""
    users_df, sessions_df = generated_data
    val_results = validate_dataset(sessions_df, users_df)

    assert len(val_results) == 11
    for rule_name, rule_res in val_results.items():
        assert rule_res["status"] is True, f"Rule {rule_name} failed: {rule_res}"


def test_statistical_quality_checks(generated_data):
    """Verify all statistical divergence checks between profiles pass."""
    _, sessions_df = generated_data
    quality_results = run_quality_checks(sessions_df)

    assert quality_results["variance_check"]["passed"] is True
    assert quality_results["weekend_shifter_check"]["passed"] is True
    assert quality_results["heavy_screen_check"]["passed"] is True
    assert quality_results["topup_vs_heavy_soc_check"]["passed"] is True
