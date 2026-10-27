"""
Smart Battery AI - Personalized Historical Feature Engineering
==============================================================
Generates strictly leak-free chronological rolling features capturing
individual user charging routines, weekday/weekend shifts, and recent trends.
"""

import os
import sys
from typing import List, Tuple, Dict, Any, Union
import numpy as np
import pandas as pd

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ml.preprocessing import (
    SAFE_FEATURE_COLUMNS,
    encode_cyclical_hour,
    decode_cyclical_hour,
    circular_distance_hours,
    circular_error_minutes,
    extract_safe_features,
)


PERSONALIZED_HISTORICAL_FEATURE_COLUMNS: List[str] = [
    "user_hist_unplug_sin_mean",
    "user_hist_unplug_cos_mean",
    "user_hist_unplug_circular_std",
    "user_hist_weekday_unplug_sin_mean",
    "user_hist_weekday_unplug_cos_mean",
    "user_hist_weekend_unplug_sin_mean",
    "user_hist_weekend_unplug_cos_mean",
    "recent_3_unplug_sin_mean",
    "recent_3_unplug_cos_mean",
    "recent_7_unplug_sin_mean",
    "recent_7_unplug_cos_mean",
    "historical_start_hour_mean_sin",
    "historical_start_hour_mean_cos",
    "historical_start_soc_mean",
    "historical_previous_day_usage_mean",
    "completed_history_count",
]

ALL_PERSONALIZED_FEATURE_COLUMNS: List[str] = SAFE_FEATURE_COLUMNS + PERSONALIZED_HISTORICAL_FEATURE_COLUMNS


def circular_blend_predictions(
    global_hours: Union[float, np.ndarray, pd.Series],
    personalized_hours: Union[float, np.ndarray, pd.Series],
    history_counts: Union[int, float, np.ndarray, pd.Series],
    threshold: float = 7.0,
    period: float = 24.0,
) -> Union[float, np.ndarray]:
    """
    Blends global model predictions with personalized model predictions
    using circular vector weighting based on completed history count.

    Weight formula: w = min(history_count / threshold, 1.0)
    For w = 0.5 with 23:30 (23.5) and 00:30 (0.5), correctly produces 00:00 (Midnight).
    """
    g_arr = np.asarray(global_hours, dtype=np.float64)
    p_arr = np.asarray(personalized_hours, dtype=np.float64)
    c_arr = np.asarray(history_counts, dtype=np.float64)

    # Calculate weight: 0 history -> 0.0, 7+ history -> 1.0
    weights = np.clip(c_arr / max(threshold, 1e-6), 0.0, 1.0)

    # Convert to unit vectors
    g_angles = g_arr * (2.0 * np.pi / period)
    p_angles = p_arr * (2.0 * np.pi / period)

    g_sin, g_cos = np.sin(g_angles), np.cos(g_angles)
    p_sin, p_cos = np.sin(p_angles), np.cos(p_angles)

    v_sin = (1.0 - weights) * g_sin + weights * p_sin
    v_cos = (1.0 - weights) * g_cos + weights * p_cos

    blended = decode_cyclical_hour(v_sin, v_cos, period=period)
    if isinstance(global_hours, (float, int)) and isinstance(personalized_hours, (float, int)):
        return float(blended)
    return blended


def compute_historical_features_chronological(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes rolling historical features for each session using ONLY strictly
    prior sessions (sessions 1..n-1 for session n).
    Guarantees zero leakage from session n or future sessions.
    """
    df_sorted = df.copy()
    if "charging_start_time" in df_sorted.columns:
        df_sorted["_sort_time"] = pd.to_datetime(df_sorted["charging_start_time"])
    else:
        df_sorted["_sort_time"] = pd.to_datetime(df_sorted["date"]) + pd.to_timedelta(df_sorted["charging_start_hour"], unit="h")

    # Sort strictly by user and time
    original_index = df_sorted.index
    df_sorted = df_sorted.sort_values(by=["user_id", "_sort_time"]).reset_index(drop=False)

    n = len(df_sorted)

    # Pre-extract target angles
    if "unplug_hour" in df_sorted.columns:
        unplug_hours = df_sorted["unplug_hour"].values
    else:
        unplug_dt = pd.to_datetime(df_sorted["unplug_time"])
        unplug_hours = (unplug_dt.dt.hour + unplug_dt.dt.minute / 60.0 + unplug_dt.dt.second / 3600.0).values

    angles = unplug_hours * (2.0 * np.pi / 24.0)
    sin_unplugs = np.sin(angles)
    cos_unplugs = np.cos(angles)

    # Start hour angles
    start_hours = df_sorted["charging_start_hour"].values if "charging_start_hour" in df_sorted.columns else pd.to_datetime(df_sorted["charging_start_time"]).dt.hour.values
    start_angles = start_hours * (2.0 * np.pi / 24.0)
    sin_starts = np.sin(start_angles)
    cos_starts = np.cos(start_angles)

    is_weekends = df_sorted["is_weekend"].values if "is_weekend" in df_sorted.columns else (pd.to_datetime(df_sorted["_sort_time"]).dt.weekday >= 5).astype(int).values
    start_socs = df_sorted["start_battery_percent"].values
    prev_usages = df_sorted["previous_day_usage_minutes"].fillna(350.0).values if "previous_day_usage_minutes" in df_sorted.columns else np.full(n, 350.0)

    # Pre-allocate output arrays
    f_hist_sin = np.zeros(n, dtype=np.float64)
    f_hist_cos = np.zeros(n, dtype=np.float64)
    f_hist_std = np.zeros(n, dtype=np.float64)
    f_weekday_sin = np.zeros(n, dtype=np.float64)
    f_weekday_cos = np.zeros(n, dtype=np.float64)
    f_weekend_sin = np.zeros(n, dtype=np.float64)
    f_weekend_cos = np.zeros(n, dtype=np.float64)
    f_rec3_sin = np.zeros(n, dtype=np.float64)
    f_rec3_cos = np.zeros(n, dtype=np.float64)
    f_rec7_sin = np.zeros(n, dtype=np.float64)
    f_rec7_cos = np.zeros(n, dtype=np.float64)
    f_hist_start_sin = np.zeros(n, dtype=np.float64)
    f_hist_start_cos = np.zeros(n, dtype=np.float64)
    f_hist_soc = np.zeros(n, dtype=np.float64)
    f_hist_usage = np.zeros(n, dtype=np.float64)
    f_count = np.zeros(n, dtype=np.float64)

    # Population cold-start priors (derived from global baseline)
    POP_MEAN_HOUR = 8.68  # Circular global mean ~08:41
    pop_angle = POP_MEAN_HOUR * (2.0 * np.pi / 24.0)
    pop_sin = float(np.sin(pop_angle))
    pop_cos = float(np.cos(pop_angle))
    pop_std = 3.58
    pop_soc = 41.0
    pop_usage = 350.0

    # Group by user and iterate chronologically
    for uid, grp in df_sorted.groupby("user_id"):
        indices = grp.index.values
        m = len(indices)

        u_sin = sin_unplugs[indices]
        u_cos = cos_unplugs[indices]
        u_start_sin = sin_starts[indices]
        u_start_cos = cos_starts[indices]
        u_we = is_weekends[indices]
        u_soc = start_socs[indices]
        u_usage = prev_usages[indices]

        for i in range(m):
            row_idx = indices[i]
            f_count[row_idx] = float(i)

            if i == 0:
                # 0 previous sessions: Cold-start population defaults
                f_hist_sin[row_idx] = pop_sin
                f_hist_cos[row_idx] = pop_cos
                f_hist_std[row_idx] = pop_std
                f_weekday_sin[row_idx] = pop_sin
                f_weekday_cos[row_idx] = pop_cos
                f_weekend_sin[row_idx] = pop_sin
                f_weekend_cos[row_idx] = pop_cos
                f_rec3_sin[row_idx] = pop_sin
                f_rec3_cos[row_idx] = pop_cos
                f_rec7_sin[row_idx] = pop_sin
                f_rec7_cos[row_idx] = pop_cos
                f_hist_start_sin[row_idx] = 0.0
                f_hist_start_cos[row_idx] = 1.0
                f_hist_soc[row_idx] = pop_soc
                f_hist_usage[row_idx] = pop_usage
                continue

            # Prior slices strictly covering sessions 0 .. i-1
            past_sin = u_sin[:i]
            past_cos = u_cos[:i]
            sum_s = np.sum(past_sin)
            sum_c = np.sum(past_cos)
            R = np.sqrt(sum_s**2 + sum_c**2) / float(i)
            r_norm = max(np.sqrt(sum_s**2 + sum_c**2), 1e-9)
            f_hist_sin[row_idx] = sum_s / r_norm
            f_hist_cos[row_idx] = sum_c / r_norm
            f_hist_std[row_idx] = np.sqrt(max(0.0, -2.0 * np.log(max(R, 1e-10)))) * (24.0 / (2.0 * np.pi))

            # Weekday & Weekend prior sessions
            past_we = u_we[:i]
            wd_mask = (past_we == 0)
            we_mask = (past_we == 1)

            if np.any(wd_mask):
                ws = np.sum(past_sin[wd_mask])
                wc = np.sum(past_cos[wd_mask])
                wr = max(np.sqrt(ws**2 + wc**2), 1e-9)
                f_weekday_sin[row_idx] = ws / wr
                f_weekday_cos[row_idx] = wc / wr
            else:
                f_weekday_sin[row_idx] = f_hist_sin[row_idx]
                f_weekday_cos[row_idx] = f_hist_cos[row_idx]

            if np.any(we_mask):
                es = np.sum(past_sin[we_mask])
                ec = np.sum(past_cos[we_mask])
                er = max(np.sqrt(es**2 + ec**2), 1e-9)
                f_weekend_sin[row_idx] = es / er
                f_weekend_cos[row_idx] = ec / er
            else:
                f_weekend_sin[row_idx] = f_hist_sin[row_idx]
                f_weekend_cos[row_idx] = f_hist_cos[row_idx]

            # Recent 3 and 7 sessions
            k3 = min(3, i)
            s3 = np.sum(u_sin[i-k3:i])
            c3 = np.sum(u_cos[i-k3:i])
            r3 = max(np.sqrt(s3**2 + c3**2), 1e-9)
            f_rec3_sin[row_idx] = s3 / r3
            f_rec3_cos[row_idx] = c3 / r3

            k7 = min(7, i)
            s7 = np.sum(u_sin[i-k7:i])
            c7 = np.sum(u_cos[i-k7:i])
            r7 = max(np.sqrt(s7**2 + c7**2), 1e-9)
            f_rec7_sin[row_idx] = s7 / r7
            f_rec7_cos[row_idx] = c7 / r7

            # Prior plug-in start hour, start SOC, and screen usage
            s_start = np.sum(u_start_sin[:i])
            c_start = np.sum(u_start_cos[:i])
            r_start = max(np.sqrt(s_start**2 + c_start**2), 1e-9)
            f_hist_start_sin[row_idx] = s_start / r_start
            f_hist_start_cos[row_idx] = c_start / r_start
            f_hist_soc[row_idx] = float(np.mean(u_soc[:i]))
            f_hist_usage[row_idx] = float(np.mean(u_usage[:i]))

    # Construct dataframe in sorted order, then restore original order
    hist_dict = {
        "user_hist_unplug_sin_mean": f_hist_sin,
        "user_hist_unplug_cos_mean": f_hist_cos,
        "user_hist_unplug_circular_std": f_hist_std,
        "user_hist_weekday_unplug_sin_mean": f_weekday_sin,
        "user_hist_weekday_unplug_cos_mean": f_weekday_cos,
        "user_hist_weekend_unplug_sin_mean": f_weekend_sin,
        "user_hist_weekend_unplug_cos_mean": f_weekend_cos,
        "recent_3_unplug_sin_mean": f_rec3_sin,
        "recent_3_unplug_cos_mean": f_rec3_cos,
        "recent_7_unplug_sin_mean": f_rec7_sin,
        "recent_7_unplug_cos_mean": f_rec7_cos,
        "historical_start_hour_mean_sin": f_hist_start_sin,
        "historical_start_hour_mean_cos": f_hist_start_cos,
        "historical_start_soc_mean": f_hist_soc,
        "historical_previous_day_usage_mean": f_hist_usage,
        "completed_history_count": f_count,
    }

    hist_df_sorted = pd.DataFrame(hist_dict, index=df_sorted["index"])
    hist_df = hist_df_sorted.loc[original_index].reset_index(drop=True)
    return hist_df


def extract_all_personalized_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts complete 26-feature matrix combining base safe features
    and leak-free historical personalized features.
    """
    base_features = extract_safe_features(df)

    # Check if historical features already precomputed in df
    missing_hist_cols = [c for c in PERSONALIZED_HISTORICAL_FEATURE_COLUMNS if c not in df.columns]
    if missing_hist_cols:
        hist_features = compute_historical_features_chronological(df)
    else:
        hist_features = df[PERSONALIZED_HISTORICAL_FEATURE_COLUMNS].copy()

    # Reindex to match base_features
    hist_features.index = base_features.index
    combined = pd.concat([base_features, hist_features], axis=1)
    return combined[ALL_PERSONALIZED_FEATURE_COLUMNS]
