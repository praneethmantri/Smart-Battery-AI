"""
Smart Battery AI - ML Model Architecture & Inference
====================================================
Provides dual-target circular regressors, naive circular baseline,
serialization utilities, and the UnplugPredictor service class.
"""

from datetime import datetime, timedelta
import json
import os
from typing import Tuple, Optional, Any, Dict
import numpy as np
import pandas as pd
import joblib

from ml.preprocessing import (
    SAFE_FEATURE_COLUMNS,
    decode_cyclical_hour,
    extract_safe_features,
)


class NaiveBaselinePredictor:
    """
    Naive baseline that always predicts the global directional circular mean
    unplug hour learned from training data.
    """

    def __init__(self):
        self.mean_sin: float = 0.0
        self.mean_cos: float = 1.0
        self.mean_hour: float = 8.0

    def fit(self, X: Any, target_sin: np.ndarray, target_cos: np.ndarray) -> "NaiveBaselinePredictor":
        """Learns the directional circular mean of training targets."""
        sin_arr = np.asarray(target_sin, dtype=np.float64)
        cos_arr = np.asarray(target_cos, dtype=np.float64)

        mean_s = float(np.mean(sin_arr))
        mean_c = float(np.mean(cos_arr))

        # Normalize vector
        r = np.sqrt(mean_s**2 + mean_c**2)
        if r > 1e-9:
            self.mean_sin = mean_s / r
            self.mean_cos = mean_c / r
        else:
            self.mean_sin = 0.0
            self.mean_cos = 1.0

        self.mean_hour = float(decode_cyclical_hour(self.mean_sin, self.mean_cos, period=24.0))
        return self

    def predict_components(self, X: Any) -> Tuple[np.ndarray, np.ndarray]:
        n = len(X)
        return np.full(n, self.mean_sin, dtype=np.float64), np.full(n, self.mean_cos, dtype=np.float64)

    def predict_hour(self, X: Any) -> np.ndarray:
        n = len(X)
        return np.full(n, self.mean_hour, dtype=np.float64)


class CircularTargetRegressor:
    """
    Composite regressor that fits separate regressors for target_sin and target_cos,
    then decodes their outputs into continuous clock hours [0.0, 24.0).
    """

    def __init__(self, model_sin: Any, model_cos: Any, name: str = "CircularRegressor"):
        self.model_sin = model_sin
        self.model_cos = model_cos
        self.name = name

    def fit(self, X: pd.DataFrame, target_sin: np.ndarray, target_cos: np.ndarray) -> "CircularTargetRegressor":
        """Fits both underlying regressors."""
        self.model_sin.fit(X, target_sin)
        self.model_cos.fit(X, target_cos)
        return self

    def predict_components(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Predicts raw sine and cosine vector components."""
        sin_pred = self.model_sin.predict(X)
        cos_pred = self.model_cos.predict(X)
        return sin_pred, cos_pred

    def predict_hour(self, X: pd.DataFrame) -> np.ndarray:
        """Predicts clock hour in [0.0, 24.0) using atan2 decoding."""
        sin_pred, cos_pred = self.predict_components(X)
        return decode_cyclical_hour(sin_pred, cos_pred, period=24.0)


def save_circular_model(
    model_sin: Any,
    model_cos: Any,
    metadata: Dict[str, Any],
    model_dir: str = "ml/models",
) -> None:
    """
    Serializes dual-target model artifacts and metadata.
    """
    os.makedirs(model_dir, exist_ok=True)
    sin_path = os.path.join(model_dir, "unplug_sin_model.joblib")
    cos_path = os.path.join(model_dir, "unplug_cos_model.joblib")
    meta_path = os.path.join(model_dir, "model_metadata.json")

    joblib.dump(model_sin, sin_path)
    joblib.dump(model_cos, cos_path)

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)


def load_circular_model(model_dir: str = "ml/models") -> Tuple[Any, Any, Dict[str, Any]]:
    """
    Loads saved dual-target model artifacts and metadata.
    """
    sin_path = os.path.join(model_dir, "unplug_sin_model.joblib")
    cos_path = os.path.join(model_dir, "unplug_cos_model.joblib")
    meta_path = os.path.join(model_dir, "model_metadata.json")

    if not (os.path.exists(sin_path) and os.path.exists(cos_path)):
        raise FileNotFoundError(f"Missing model artifacts in {model_dir}")

    model_sin = joblib.load(sin_path)
    model_cos = joblib.load(cos_path)

    metadata = {}
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

    return model_sin, model_cos, metadata


class UnplugPredictor:
    """
    High-level inference service for loading trained models and predicting
    unplug datetime and confidence score.

    Supports:
    1. Dual circular models (ml/models/unplug_sin_model.joblib & unplug_cos_model.joblib)
    2. Legacy single model (ml/artifacts/unplug_predictor.joblib)
    3. Heuristic rule-based fallback
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        model_dir: str = "ml/models",
    ):
        self.model_dir = model_dir
        self.model_path = model_path
        self.model_sin = None
        self.model_cos = None
        self.legacy_model = None
        self.metadata = {}
        self._load_models()

    def _load_models(self) -> None:
        """Attempts to load models according to configuration."""
        # If an explicit model_path was specified, only load that specific artifact
        if self.model_path is not None:
            if os.path.exists(self.model_path):
                try:
                    self.legacy_model = joblib.load(self.model_path)
                except Exception:
                    self.legacy_model = None
            return

        # Default: check circular models in model_dir
        sin_path = os.path.join(self.model_dir, "unplug_sin_model.joblib")
        cos_path = os.path.join(self.model_dir, "unplug_cos_model.joblib")
        if os.path.exists(sin_path) and os.path.exists(cos_path):
            try:
                self.model_sin = joblib.load(sin_path)
                self.model_cos = joblib.load(cos_path)
                meta_path = os.path.join(self.model_dir, "model_metadata.json")
                if os.path.exists(meta_path):
                    with open(meta_path, "r", encoding="utf-8") as f:
                        self.metadata = json.load(f)
                return
            except Exception:
                self.model_sin = None
                self.model_cos = None

        # Fallback to legacy default path if exists
        legacy_default = "ml/artifacts/unplug_predictor.joblib"
        if os.path.exists(legacy_default):
            try:
                self.legacy_model = joblib.load(legacy_default)
            except Exception:
                self.legacy_model = None

    def is_loaded(self) -> bool:
        """Returns True if a trained ML model (circular or legacy) is ready."""
        return (self.model_sin is not None and self.model_cos is not None) or (self.legacy_model is not None)

    def predict(
        self,
        user_id: str,
        plug_time: datetime,
        start_battery_pct: float = 50.0,
        charger_type: str = "standard",
        previous_day_usage_minutes: float = 300.0,
    ) -> Tuple[datetime, float]:
        """
        Predicts expected unplug timestamp for a given plug event.
        Returns:
            Tuple[datetime, float]: (predicted_unplug_datetime, confidence_score)
        """
        # A. Primary: Circular Dual Regressors
        if self.model_sin is not None and self.model_cos is not None:
            raw_input = pd.DataFrame([{
                "charging_start_time": plug_time,
                "start_battery_percent": start_battery_pct,
                "charger_type": charger_type,
                "weekday": plug_time.weekday(),
                "is_weekend": 1 if plug_time.weekday() >= 5 else 0,
                "previous_day_usage_minutes": previous_day_usage_minutes,
            }])

            X = extract_safe_features(raw_input)
            sin_val = float(self.model_sin.predict(X)[0])
            cos_val = float(self.model_cos.predict(X)[0])
            pred_hour = float(decode_cyclical_hour(sin_val, cos_val, period=24.0))

            # Convert predicted hour of day into next future datetime
            pred_hours_int = int(pred_hour)
            pred_minutes = int((pred_hour - pred_hours_int) * 60.0)
            pred_seconds = int((((pred_hour - pred_hours_int) * 60.0) - pred_minutes) * 60.0)

            # Candidate datetime on the same calendar date
            candidate_dt = plug_time.replace(
                hour=pred_hours_int,
                minute=pred_minutes,
                second=pred_seconds,
                microsecond=0,
            )

            # If candidate is earlier than or equal to plug_time, it must occur the next calendar day
            if candidate_dt <= plug_time:
                candidate_dt += timedelta(days=1)

            # Confidence based on test accuracy (derived from metadata or high default)
            confidence = float(self.metadata.get("metrics", {}).get("within_60_min_pct", 85.0)) / 100.0
            confidence = max(0.60, min(0.95, confidence))
            return candidate_dt, round(confidence, 2)

        # B. Legacy pipeline fallback
        if self.legacy_model is not None:
            from ml.feature_engineering import extract_features_from_timestamp
            features = extract_features_from_timestamp(plug_time, start_battery_pct)
            predicted_duration_hours = float(self.legacy_model.predict(features)[0])
            predicted_duration_hours = max(0.25, min(24.0, predicted_duration_hours))
            predicted_unplug = plug_time + timedelta(hours=predicted_duration_hours)
            return predicted_unplug, 0.88

        # C. Heuristic Rule-Based Fallback
        hour = plug_time.hour
        if hour >= 21 or hour < 5:
            # Overnight schedule: target ~07:30 AM
            target_date = plug_time.date() if hour < 5 else (plug_time + timedelta(days=1)).date()
            predicted_unplug = plug_time.replace(
                year=target_date.year,
                month=target_date.month,
                day=target_date.day,
                hour=7,
                minute=30,
                second=0,
                microsecond=0,
            )
            confidence = 0.70
        else:
            # Daytime top-up session: ~2.0 hours
            predicted_unplug = plug_time + timedelta(hours=2.0)
            confidence = 0.60

        return predicted_unplug, confidence
