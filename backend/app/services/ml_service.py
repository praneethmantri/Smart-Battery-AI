"""
Smart Battery AI - Production ML Inference Service
==================================================
Manages cached model artifacts, feature schema verification, and
intelligent cold-start / personalized unplug-time inference.

Loads models once on application startup or first access:
- Global Circular Models: unplug_sin_model.joblib & unplug_cos_model.joblib
- Personalized Circular Models: personalized_unplug_sin_model.joblib & personalized_unplug_cos_model.joblib

Strategy Selection:
- 0 to 2 completed historical sessions: GLOBAL_BASELINE
- 3 to 6 completed historical sessions: BLENDED
- 7+ completed historical sessions:    PERSONALIZED
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import logging
import os
from typing import Optional, List, Dict, Any, Tuple
import joblib
import numpy as np
import pandas as pd

from app.core.config import settings
from app.models.charging_session import ChargingSession
from app.schemas.recommendation import PredictionSource, ConfidenceLevel
from app.services.feature_service import (
    feature_service,
    SAFE_FEATURE_COLUMNS,
    ALL_PERSONALIZED_FEATURE_COLUMNS,
)

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """Standardized output of the ML prediction pipeline."""
    user_id: int
    predicted_unplug_time_str: str  # "HH:MM" format
    predicted_unplug_hour: float    # Continuous hour in [0, 24)
    predicted_unplug_datetime: datetime
    prediction_source: str          # GLOBAL_BASELINE, BLENDED, PERSONALIZED, RULE_BASED
    confidence_score: float         # [0.0, 1.0]
    confidence_level: str           # HIGH, MEDIUM, LOW
    history_count: int
    model_version: str
    circular_std: float


class MLService:
    """
    Singleton service that holds loaded ML models in memory, validates schemas,
    and executes fast, safe inference.
    """

    def __init__(self):
        self._models_loaded: bool = False
        self.global_sin_model: Optional[Any] = None
        self.global_cos_model: Optional[Any] = None
        self.global_metadata: Dict[str, Any] = {}

        self.pers_sin_model: Optional[Any] = None
        self.pers_cos_model: Optional[Any] = None
        self.pers_metadata: Dict[str, Any] = {}

    def load_models(self) -> None:
        """
        Loads all model artifacts from the resolved model directory.
        Safe against missing files; provides graceful fallback.
        """
        if self._models_loaded:
            return

        model_dir: Path = settings.resolved_model_dir
        logger.info("Loading ML models from: %s", str(model_dir))

        if not model_dir.exists():
            logger.warning("Model directory does not exist: %s. Using rule-based fallback.", str(model_dir))
            self._models_loaded = True
            return

        # 1. Load Global Baseline Models
        g_sin_path = model_dir / "unplug_sin_model.joblib"
        g_cos_path = model_dir / "unplug_cos_model.joblib"
        g_meta_path = model_dir / "model_metadata.json"

        if g_sin_path.exists() and g_cos_path.exists():
            try:
                self.global_sin_model = joblib.load(g_sin_path)
                self.global_cos_model = joblib.load(g_cos_path)
                if g_meta_path.exists():
                    with open(g_meta_path, "r", encoding="utf-8") as f:
                        self.global_metadata = json.load(f)
                logger.info("Global baseline circular ML models loaded successfully.")
                self._verify_global_feature_schema()
            except Exception as exc:
                logger.error("Failed to load global baseline models: %s", str(exc))
                self.global_sin_model = None
                self.global_cos_model = None
        else:
            logger.warning("Global model artifacts missing at %s", str(model_dir))

        # 2. Load Personalized Models
        p_sin_path = model_dir / "personalized_unplug_sin_model.joblib"
        p_cos_path = model_dir / "personalized_unplug_cos_model.joblib"
        p_meta_path = model_dir / "personalized_model_metadata.json"

        if p_sin_path.exists() and p_cos_path.exists():
            try:
                self.pers_sin_model = joblib.load(p_sin_path)
                self.pers_cos_model = joblib.load(p_cos_path)
                if p_meta_path.exists():
                    with open(p_meta_path, "r", encoding="utf-8") as f:
                        self.pers_metadata = json.load(f)
                logger.info("Personalized circular ML models loaded successfully.")
                self._verify_personalized_feature_schema()
            except Exception as exc:
                logger.error("Failed to load personalized models: %s", str(exc))
                self.pers_sin_model = None
                self.pers_cos_model = None
        else:
            logger.warning("Personalized model artifacts missing at %s", str(model_dir))

        self._models_loaded = True

    def _verify_global_feature_schema(self) -> None:
        """Verifies feature alignment with global model metadata."""
        if not self.global_metadata or "features" not in self.global_metadata:
            return
        expected = self.global_metadata["features"]
        if expected != SAFE_FEATURE_COLUMNS:
            err = f"Global model feature schema mismatch! Expected {expected}, got {SAFE_FEATURE_COLUMNS}"
            logger.error(err)
            raise RuntimeError(err)

    def _verify_personalized_feature_schema(self) -> None:
        """Verifies feature alignment with personalized model metadata."""
        if not self.pers_metadata or "features" not in self.pers_metadata:
            return
        expected = self.pers_metadata["features"]
        if expected != ALL_PERSONALIZED_FEATURE_COLUMNS:
            err = f"Personalized feature schema mismatch! Expected {expected}, got {ALL_PERSONALIZED_FEATURE_COLUMNS}"
            logger.error(err)
            raise RuntimeError(err)

    @property
    def global_loaded(self) -> bool:
        self.load_models()
        return self.global_sin_model is not None and self.global_cos_model is not None

    @property
    def personalized_loaded(self) -> bool:
        self.load_models()
        return self.pers_sin_model is not None and self.pers_cos_model is not None

    def get_health_status(self) -> Dict[str, str]:
        """Provides status of model artifacts for health checks."""
        return {
            "global_model": "loaded" if self.global_loaded else "unavailable",
            "personalized_model": "loaded" if self.personalized_loaded else "unavailable",
        }

    def decode_cyclical_hour(self, sin_val: float, cos_val: float) -> float:
        """Converts sine and cosine components back to continuous hour [0.0, 24.0)."""
        angle = np.arctan2(sin_val, cos_val)
        if angle < 0:
            angle += 2.0 * np.pi
        hour = float(angle * (24.0 / (2.0 * np.pi)))
        return hour % 24.0

    def circular_blend(self, g_hour: float, p_hour: float, history_count: int, threshold: float = 7.0) -> float:
        """Blends global and personalized predictions using circular vector weighting."""
        weight = min(float(history_count) / max(threshold, 1e-6), 1.0)
        g_ang = g_hour * (2.0 * np.pi / 24.0)
        p_ang = p_hour * (2.0 * np.pi / 24.0)

        g_s, g_c = np.sin(g_ang), np.cos(g_ang)
        p_s, p_c = np.sin(p_ang), np.cos(p_ang)

        v_s = (1.0 - weight) * g_s + weight * p_s
        v_c = (1.0 - weight) * g_c + weight * p_c

        return self.decode_cyclical_hour(float(v_s), float(v_c))

    def predict(
        self,
        user_id: int,
        plug_time: Optional[datetime] = None,
        start_battery_pct: float = 50.0,
        charger_type: Optional[str] = "standard",
        history_sessions: Optional[List[ChargingSession]] = None,
        previous_day_usage_minutes: Optional[float] = None,
    ) -> PredictionResult:
        """
        Executes end-to-end unplug prediction with cold-start, blended,
        or personalized inference based on completed history depth.

        AUDIT ON CONSUMING REAL WINDOWS TELEMETRY:
        - Structural Safety: Safe. Feature transformations (circular sin/cos, mean SOC,
          circular variance) map cleanly within [-1.0, 1.0] and [0.0, 100.0]. The model
          will not crash or produce numerical instability on real Windows sessions.
        - Domain Shift Disclaimer: Model weights were fitted on synthetic Gaussian distributions.
          Real user behavior involves lid-closure sleep states, variable laptop USB-C wattage,
          and irregular travel disconnections. Do NOT assume synthetic benchmark accuracy transfers
          directly to real users until 7-14 days of real sessions are accumulated for re-evaluation.
        """
        self.load_models()

        if plug_time is None:
            plug_time = datetime.now(timezone.utc)
        elif plug_time.tzinfo is None:
            plug_time = plug_time.replace(tzinfo=timezone.utc)

        # 1. Extract inference features via FeatureService
        feat_res = feature_service.extract_features(
            user_id=user_id,
            plug_time=plug_time,
            start_battery_pct=start_battery_pct,
            charger_type=charger_type,
            previous_day_usage_minutes=previous_day_usage_minutes,
            history_sessions=history_sessions,
        )

        history_count = feat_res.history_count
        circular_std = feat_res.circular_std

        # 2. Heuristic fallback if models not loaded
        if not self.global_loaded:
            hour = plug_time.hour
            tz = plug_time.tzinfo or timezone.utc
            if hour >= 21 or hour < 5:
                target_date = plug_time.date() if hour < 5 else (plug_time + timedelta(days=1)).date()
                pred_dt = datetime(target_date.year, target_date.month, target_date.day, 7, 30, tzinfo=tz)
                pred_hour = 7.5
                conf = 0.75
            else:
                pred_dt = plug_time + timedelta(hours=2.0)
                pred_hour = float((pred_dt.hour + pred_dt.minute / 60.0) % 24.0)
                conf = 0.60

            while pred_dt <= plug_time:
                pred_dt += timedelta(days=1)

            return PredictionResult(
                user_id=user_id,
                predicted_unplug_time_str=pred_dt.strftime("%H:%M"),
                predicted_unplug_hour=round(pred_hour, 2),
                predicted_unplug_datetime=pred_dt,
                prediction_source=PredictionSource.RULE_BASED.value,
                confidence_score=conf,
                confidence_level=ConfidenceLevel.MEDIUM.value if conf >= 0.65 else ConfidenceLevel.LOW.value,
                history_count=history_count,
                model_version="heuristic-fallback",
                circular_std=circular_std,
            )

        # 3. Compute Global Prediction
        g_s = float(self.global_sin_model.predict(feat_res.base_features)[0])
        g_c = float(self.global_cos_model.predict(feat_res.base_features)[0])
        global_hour = self.decode_cyclical_hour(g_s, g_c)

        # 4. Determine Strategy Tier
        # Tier 1: Cold start (0-2 sessions) or personalized models unavailable -> GLOBAL_BASELINE
        if history_count < 3 or not self.personalized_loaded:
            pred_hour = global_hour
            source = PredictionSource.GLOBAL_BASELINE.value
            model_ver = self.global_metadata.get("model_version", "1.0.0-baseline-global")
            # Base accuracy ~83.9%
            base_conf = float(self.global_metadata.get("metrics", {}).get("within_60_min_pct", 83.9)) / 100.0
            conf_score = round(max(0.60, min(0.90, base_conf - (0.05 if history_count == 0 else 0.0))), 2)

        # Tier 2: Blended Progression (3-6 sessions)
        elif 3 <= history_count < 7:
            p_s = float(self.pers_sin_model.predict(feat_res.personalized_features)[0])
            p_c = float(self.pers_cos_model.predict(feat_res.personalized_features)[0])
            pers_hour = self.decode_cyclical_hour(p_s, p_c)

            pred_hour = self.circular_blend(global_hour, pers_hour, history_count, threshold=7.0)
            source = PredictionSource.BLENDED.value
            model_ver = self.pers_metadata.get("model_version", "2.0.0-personalized")
            w = float(history_count) / 7.0
            conf_score = round(0.80 + (w * 0.07), 2)

        # Tier 3: Full Personalization (7+ sessions)
        else:
            p_s = float(self.pers_sin_model.predict(feat_res.personalized_features)[0])
            p_c = float(self.pers_cos_model.predict(feat_res.personalized_features)[0])
            pred_hour = self.decode_cyclical_hour(p_s, p_c)
            source = PredictionSource.PERSONALIZED.value
            model_ver = self.pers_metadata.get("model_version", "2.0.0-personalized")

            base_conf = float(self.pers_metadata.get("metrics", {}).get("within_60_min_pct", 87.37)) / 100.0
            # Scale confidence slightly downward if user schedule has high variance
            variance_penalty = max(0.0, circular_std - 1.5) * 0.05
            conf_score = round(max(0.55, min(0.95, base_conf - variance_penalty)), 2)

        # Ensure bounds [0, 24)
        pred_hour = float(pred_hour % 24.0)

        # 5. Convert predicted hour of day into next future datetime
        pred_h_int = int(pred_hour)
        pred_m_int = int((pred_hour - pred_h_int) * 60.0)

        candidate_dt = plug_time.replace(hour=pred_h_int, minute=pred_m_int, second=0, microsecond=0)
        while candidate_dt <= plug_time:
            candidate_dt += timedelta(days=1)
        time_str = f"{candidate_dt.hour:02d}:{candidate_dt.minute:02d}"

        # 6. Confidence Categorization
        if circular_std >= 1.5:
            conf_level = ConfidenceLevel.LOW.value
        elif conf_score >= 0.80:
            conf_level = ConfidenceLevel.HIGH.value
        elif conf_score >= 0.65:
            conf_level = ConfidenceLevel.MEDIUM.value
        else:
            conf_level = ConfidenceLevel.LOW.value

        logger.info(
            "Prediction generated for user %d: hour=%.2f (%s) | source=%s | conf=%.2f (%s) | history=%d",
            user_id, pred_hour, time_str, source, conf_score, conf_level, history_count
        )

        return PredictionResult(
            user_id=user_id,
            predicted_unplug_time_str=time_str,
            predicted_unplug_hour=round(pred_hour, 2),
            predicted_unplug_datetime=candidate_dt,
            prediction_source=source,
            confidence_score=conf_score,
            confidence_level=conf_level,
            history_count=history_count,
            model_version=model_ver,
            circular_std=circular_std,
        )


ml_service = MLService()
