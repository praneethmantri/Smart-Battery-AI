from datetime import datetime
import numpy as np
import pandas as pd


def extract_features_from_timestamp(dt: datetime, start_battery_pct: float = 50.0) -> pd.DataFrame:
    """
    Transforms a single plug-in timestamp into cyclical and categorical features.
    
    Returns a 1-row DataFrame ready for Scikit-learn pipeline inference.
    """
    hour_val = dt.hour + dt.minute / 60.0
    day_of_week = dt.weekday()
    is_weekend = 1 if day_of_week >= 5 else 0

    # Sine and Cosine cyclic encoding for 24-hour periodicity
    sin_hour = np.sin(2 * np.pi * hour_val / 24.0)
    cos_hour = np.cos(2 * np.pi * hour_val / 24.0)

    features = {
        "sin_hour": [sin_hour],
        "cos_hour": [cos_hour],
        "day_of_week": [day_of_week],
        "is_weekend": [is_weekend],
        "start_battery_pct": [start_battery_pct],
    }
    return pd.DataFrame(features)


def prepare_training_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Prepares features X and target y (duration in hours) from raw historical charging dataframe.
    """
    df["plug_time"] = pd.to_datetime(df["plug_time"])
    df["unplug_time"] = pd.to_datetime(df["unplug_time"])

    # Target: charging duration in hours
    if "duration_hours" not in df.columns:
        df["duration_hours"] = (df["unplug_time"] - df["plug_time"]).dt.total_seconds() / 3600.0

    hour_val = df["plug_time"].dt.hour + df["plug_time"].dt.minute / 60.0
    df["sin_hour"] = np.sin(2 * np.pi * hour_val / 24.0)
    df["cos_hour"] = np.cos(2 * np.pi * hour_val / 24.0)
    df["day_of_week"] = df["plug_time"].dt.weekday
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    feature_cols = ["sin_hour", "cos_hour", "day_of_week", "is_weekend", "start_battery_pct"]
    X = df[feature_cols]
    y = df["duration_hours"]

    return X, y
