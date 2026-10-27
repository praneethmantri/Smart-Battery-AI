"""
Smart Battery AI - ML Preprocessing & Feature Engineering
=========================================================
Implements leak-free feature preprocessing, cyclical time transformations,
and chronological train/test splitting.
"""

from typing import Tuple, Union, Dict, List
import numpy as np
import pandas as pd


# Canonical feature column names used across training and inference
SAFE_FEATURE_COLUMNS: List[str] = [
    "start_hour_sin",
    "start_hour_cos",
    "start_battery_percent",
    "charger_type_fast",
    "charger_type_slow",
    "charger_type_standard",
    "weekday_sin",
    "weekday_cos",
    "is_weekend",
    "previous_day_usage_minutes",
]

# Explicitly excluded leaking and synthetic features
EXCLUDED_LEAKAGE_COLUMNS: List[str] = [
    "charging_duration_minutes",  # Direct target leakage
    "end_battery_percent",        # Unknown until session end
    "average_temperature",       # Session-wide aggregate
    "screen_usage_minutes",       # Final daily cumulative
    "profile_type",               # Synthetic ground truth
    "session_id",                 # Non-predictive identifier
]


def encode_cyclical_hour(
    hour: Union[float, int, np.ndarray, pd.Series],
    period: float = 24.0,
) -> Tuple[Union[float, np.ndarray], Union[float, np.ndarray]]:
    """
    Transforms continuous clock hour (0..24) into sine and cosine orthogonal coordinates.
    Preserves distance continuity across midnight (e.g. 23:50 to 00:10).
    """
    angles = np.asarray(hour, dtype=np.float64) * (2.0 * np.pi / period)
    sin_component = np.sin(angles)
    cos_component = np.cos(angles)

    if isinstance(hour, (float, int)):
        return float(sin_component), float(cos_component)
    return sin_component, cos_component


def decode_cyclical_hour(
    sin_component: Union[float, int, np.ndarray, pd.Series],
    cos_component: Union[float, int, np.ndarray, pd.Series],
    period: float = 24.0,
) -> Union[float, np.ndarray]:
    """
    Decodes sine and cosine coordinates back into a continuous hour in [0.0, 24.0).
    Uses atan2(sin, cos) to resolve quadrant ambiguity correctly.
    """
    sin_arr = np.asarray(sin_component, dtype=np.float64)
    cos_arr = np.asarray(cos_component, dtype=np.float64)

    angles = np.arctan2(sin_arr, cos_arr)
    # Map from (-pi, pi] to [0, 2*pi)
    angles = np.where(angles < 0.0, angles + 2.0 * np.pi, angles)
    hours = angles * (period / (2.0 * np.pi))

    # Strict normalization to [0, 24)
    hours = np.mod(hours, period)

    if isinstance(sin_component, (float, int)) and isinstance(cos_component, (float, int)):
        return float(hours)
    return hours


def encode_cyclical_weekday(
    weekday: Union[int, float, np.ndarray, pd.Series],
    period: float = 7.0,
) -> Tuple[Union[float, np.ndarray], Union[float, np.ndarray]]:
    """
    Transforms day of week (0=Monday..6=Sunday) into 7-day cyclical coordinates.
    """
    angles = np.asarray(weekday, dtype=np.float64) * (2.0 * np.pi / period)
    sin_component = np.sin(angles)
    cos_component = np.cos(angles)

    if isinstance(weekday, (int, float)):
        return float(sin_component), float(cos_component)
    return sin_component, cos_component


def circular_distance_hours(
    actual: Union[float, np.ndarray, pd.Series],
    predicted: Union[float, np.ndarray, pd.Series],
    period: float = 24.0,
) -> Union[float, np.ndarray]:
    """
    Calculates the shortest angular distance between two clock times in hours.
    Correctly accounts for midnight wrap-around (e.g. 23.5 and 0.5 are 1.0 hour apart).
    """
    act = np.asarray(actual, dtype=np.float64)
    pred = np.asarray(predicted, dtype=np.float64)

    abs_diff = np.abs(act - pred) % period
    circ_dist = np.minimum(abs_diff, period - abs_diff)

    if isinstance(actual, (float, int)) and isinstance(predicted, (float, int)):
        return float(circ_dist)
    return circ_dist


def circular_error_minutes(
    actual: Union[float, np.ndarray, pd.Series],
    predicted: Union[float, np.ndarray, pd.Series],
    period: float = 24.0,
) -> Union[float, np.ndarray]:
    """
    Converts circular distance in hours to absolute error in minutes.
    """
    dist_hours = circular_distance_hours(actual, predicted, period=24.0)
    return dist_hours * 60.0


def extract_safe_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms raw input DataFrame into strictly safe features available at plug-in (t_0).
    Ensures all expected columns exist with deterministic ordering.
    """
    # 1. Start Hour Cyclical
    if "charging_start_hour" in df.columns:
        start_hour = df["charging_start_hour"].values
    elif "charging_start_time" in df.columns:
        start_dt = pd.to_datetime(df["charging_start_time"])
        start_hour = (start_dt.dt.hour + start_dt.dt.minute / 60.0 + start_dt.dt.second / 3600.0).values
    else:
        raise ValueError("Missing 'charging_start_hour' or 'charging_start_time' in input data.")

    start_hour_sin, start_hour_cos = encode_cyclical_hour(start_hour, period=24.0)

    # 2. Battery State-of-Charge at plug-in
    if "start_battery_percent" not in df.columns:
        raise ValueError("Missing 'start_battery_percent' in input data.")
    start_soc = df["start_battery_percent"].values

    # 3. Charger Type One-Hot Encoding
    charger_types = df["charger_type"].fillna("standard").astype(str).str.lower().values if "charger_type" in df.columns else np.array(["standard"] * len(df))
    is_fast = (charger_types == "fast").astype(np.float64)
    is_slow = (charger_types == "slow").astype(np.float64)
    is_standard = (charger_types == "standard").astype(np.float64)

    # 4. Weekday Cyclical
    if "weekday" in df.columns:
        weekday = df["weekday"].values
    elif "date" in df.columns:
        weekday = pd.to_datetime(df["date"]).dt.weekday.values
    elif "charging_start_time" in df.columns:
        weekday = pd.to_datetime(df["charging_start_time"]).dt.weekday.values
    else:
        weekday = np.zeros(len(df), dtype=np.float64)

    weekday_sin, weekday_cos = encode_cyclical_weekday(weekday, period=7.0)

    # 5. Weekend Indicator
    if "is_weekend" in df.columns:
        is_weekend = df["is_weekend"].astype(np.float64).values
    else:
        is_weekend = (np.asarray(weekday) >= 5).astype(np.float64)

    # 6. Previous Day Usage Minutes
    if "previous_day_usage_minutes" in df.columns:
        prev_usage = df["previous_day_usage_minutes"].fillna(300.0).values
    else:
        prev_usage = np.full(len(df), 300.0, dtype=np.float64)

    feature_dict = {
        "start_hour_sin": start_hour_sin,
        "start_hour_cos": start_hour_cos,
        "start_battery_percent": start_soc,
        "charger_type_fast": is_fast,
        "charger_type_slow": is_slow,
        "charger_type_standard": is_standard,
        "weekday_sin": weekday_sin,
        "weekday_cos": weekday_cos,
        "is_weekend": is_weekend,
        "previous_day_usage_minutes": prev_usage,
    }

    return pd.DataFrame(feature_dict, columns=SAFE_FEATURE_COLUMNS, index=df.index)


def extract_targets(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Extracts raw target hour and computes sine/cosine circular target components.
    Returns:
        (unplug_hour, target_sin, target_cos)
    """
    if "unplug_hour" in df.columns:
        unplug_hour = df["unplug_hour"].values
    elif "unplug_time" in df.columns:
        unplug_dt = pd.to_datetime(df["unplug_time"])
        unplug_hour = (unplug_dt.dt.hour + unplug_dt.dt.minute / 60.0 + unplug_dt.dt.second / 3600.0).values
    else:
        raise ValueError("Target 'unplug_hour' or 'unplug_time' not found in DataFrame.")

    target_sin, target_cos = encode_cyclical_hour(unplug_hour, period=24.0)
    return unplug_hour, target_sin, target_cos


def chronological_per_user_split(
    df: pd.DataFrame,
    train_ratio: float = 0.8,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Performs a strict chronological per-user train/test split.
    For each user:
      - Sessions are ordered by charging_start_time.
      - First 80% assigned to train.
      - Last 20% assigned to test.
    Guarantees no future sessions from any user appear in the training partition.
    """
    df_sorted = df.copy()
    if "charging_start_time" in df_sorted.columns:
        df_sorted["_sort_time"] = pd.to_datetime(df_sorted["charging_start_time"])
    else:
        df_sorted["_sort_time"] = pd.to_datetime(df_sorted["date"]) + pd.to_timedelta(df_sorted["charging_start_hour"], unit="h")

    df_sorted = df_sorted.sort_values(by=["user_id", "_sort_time"]).reset_index(drop=True)

    train_indices = []
    test_indices = []

    for uid, grp in df_sorted.groupby("user_id"):
        n_sessions = len(grp)
        split_point = int(np.floor(n_sessions * train_ratio))
        # Ensure at least 1 session in test if possible
        if split_point == n_sessions and n_sessions > 1:
            split_point = n_sessions - 1

        train_indices.extend(grp.index[:split_point])
        test_indices.extend(grp.index[split_point:])

    train_df = df_sorted.loc[train_indices].drop(columns=["_sort_time"]).reset_index(drop=True)
    test_df = df_sorted.loc[test_indices].drop(columns=["_sort_time"]).reset_index(drop=True)

    return train_df, test_df
