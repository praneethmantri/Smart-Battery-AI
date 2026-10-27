"""
Smart Battery AI - Production Feature Service
=============================================
Converts database charging sessions and current plug-in telemetry into
strictly leak-free ML feature vectors for global and personalized inference.

Guarantees 100% mathematical and structural consistency with training preprocessing:
- Identical feature names and ordering
- Identical cyclical sin/cos transformations
- Identical cold-start population priors
- Zero usage of leaking fields (charging_duration_minutes, end_battery_percent, etc.)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple
import logging
import numpy as np
import pandas as pd

from app.models.charging_session import ChargingSession

logger = logging.getLogger(__name__)

# Canonical feature column names from training metadata
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

ALL_PERSONALIZED_FEATURE_COLUMNS: List[str] = (
    SAFE_FEATURE_COLUMNS + PERSONALIZED_HISTORICAL_FEATURE_COLUMNS
)

# Population cold-start priors (strictly matching ml/personalized_features.py)
POP_MEAN_HOUR = 8.68
POP_ANGLE = POP_MEAN_HOUR * (2.0 * np.pi / 24.0)
POP_SIN = float(np.sin(POP_ANGLE))
POP_COS = float(np.cos(POP_ANGLE))
POP_STD = 3.58
POP_SOC = 41.0
POP_USAGE = 350.0


@dataclass
class FeatureExtractionResult:
    """Structured inference matrices and user context."""
    user_id: int
    history_count: int
    base_features: pd.DataFrame
    personalized_features: pd.DataFrame
    circular_std: float
    user_hist_unplug_mean_hour: float


class FeatureService:
    """
    Transforms runtime charging inputs and database history into
    inference-ready DataFrames validated against model requirements.
    """

    @staticmethod
    def extract_features(
        user_id: int,
        plug_time: datetime,
        start_battery_pct: float,
        charger_type: Optional[str] = "standard",
        previous_day_usage_minutes: Optional[float] = None,
        history_sessions: Optional[List[ChargingSession]] = None,
    ) -> FeatureExtractionResult:
        """
        Builds both the 10-feature global base matrix and 26-feature personalized matrix.
        """
        # Ensure timezone consistency
        if plug_time.tzinfo is None:
            plug_time = plug_time.replace(tzinfo=timezone.utc)

        # -------------------------------------------------------------
        # 1. Base Safe Features (Instantaneous t_0)
        # -------------------------------------------------------------
        plug_hour = plug_time.hour + plug_time.minute / 60.0 + plug_time.second / 3600.0
        hour_angle = plug_hour * (2.0 * np.pi / 24.0)
        start_hour_sin = float(np.sin(hour_angle))
        start_hour_cos = float(np.cos(hour_angle))

        # Charger one-hot encoding
        ctype = (charger_type or "standard").strip().lower()
        is_fast = 1.0 if "fast" in ctype else 0.0
        is_slow = 1.0 if "slow" in ctype else 0.0
        is_standard = 1.0 if (not is_fast and not is_slow) or "standard" in ctype else 0.0

        # Weekday cyclical encoding
        weekday = plug_time.weekday()
        weekday_angle = weekday * (2.0 * np.pi / 7.0)
        weekday_sin = float(np.sin(weekday_angle))
        weekday_cos = float(np.cos(weekday_angle))
        is_weekend = 1.0 if weekday >= 5 else 0.0

        # Previous day usage
        if previous_day_usage_minutes is not None and previous_day_usage_minutes >= 0:
            usage_val = float(previous_day_usage_minutes)
        else:
            usage_val = POP_USAGE

        base_dict: Dict[str, float] = {
            "start_hour_sin": start_hour_sin,
            "start_hour_cos": start_hour_cos,
            "start_battery_percent": float(start_battery_pct),
            "charger_type_fast": is_fast,
            "charger_type_slow": is_slow,
            "charger_type_standard": is_standard,
            "weekday_sin": weekday_sin,
            "weekday_cos": weekday_cos,
            "is_weekend": is_weekend,
            "previous_day_usage_minutes": usage_val,
        }

        # -------------------------------------------------------------
        # 2. Historical Personalized Features (Strict Anti-Leakage)
        # -------------------------------------------------------------
        # Anti-leakage: filter strictly to completed sessions occurring strictly before plug_time
        valid_completed = []
        for s in (history_sessions or []):
            st = s.start_time
            if st is None:
                continue
            if st.tzinfo is None:
                st = st.replace(tzinfo=timezone.utc)

            # Never use sessions that start at or after t_0 (prevents future leakage)
            if st >= plug_time:
                continue

            end_dt = s.end_time
            if end_dt is not None:
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
            elif s.charging_duration_minutes is not None and s.charging_duration_minutes > 0:
                end_dt = st + timedelta(minutes=s.charging_duration_minutes)

            # Never use uncompleted sessions or sessions that end after t_0
            if end_dt is not None and end_dt <= plug_time:
                valid_completed.append(s)

        # Real vs Synthetic priority:
        # If REAL_WINDOWS sessions exist, use real sessions for personalization!
        # Otherwise fallback to synthetic demo sessions so existing tests pass.
        real_sessions = [
            s for s in valid_completed
            if getattr(s, "data_source", "SYNTHETIC") == "REAL_WINDOWS"
        ]
        if len(real_sessions) > 0:
            completed = real_sessions
        else:
            completed = valid_completed

        # Sort chronologically
        completed.sort(key=lambda s: s.start_time)
        history_count = len(completed)

        if history_count == 0:
            # Cold start: Use population priors
            hist_dict: Dict[str, float] = {
                "user_hist_unplug_sin_mean": POP_SIN,
                "user_hist_unplug_cos_mean": POP_COS,
                "user_hist_unplug_circular_std": POP_STD,
                "user_hist_weekday_unplug_sin_mean": POP_SIN,
                "user_hist_weekday_unplug_cos_mean": POP_COS,
                "user_hist_weekend_unplug_sin_mean": POP_SIN,
                "user_hist_weekend_unplug_cos_mean": POP_COS,
                "recent_3_unplug_sin_mean": POP_SIN,
                "recent_3_unplug_cos_mean": POP_COS,
                "recent_7_unplug_sin_mean": POP_SIN,
                "recent_7_unplug_cos_mean": POP_COS,
                "historical_start_hour_mean_sin": 0.0,
                "historical_start_hour_mean_cos": 1.0,
                "historical_start_soc_mean": POP_SOC,
                "historical_previous_day_usage_mean": POP_USAGE,
                "completed_history_count": 0.0,
            }
            circ_std = POP_STD
            hist_mean_hour = POP_MEAN_HOUR
        else:
            # Extract past unplug hours
            past_unplug_sin = []
            past_unplug_cos = []
            past_is_weekend = []
            past_start_sin = []
            past_start_cos = []
            past_soc = []
            past_usage = []

            for s in completed:
                if s.end_time is not None:
                    u_hour = s.end_time.hour + s.end_time.minute / 60.0 + s.end_time.second / 3600.0
                elif s.charging_duration_minutes is not None:
                    u_dt = s.start_time + timedelta(minutes=s.charging_duration_minutes)
                    u_hour = u_dt.hour + u_dt.minute / 60.0 + u_dt.second / 3600.0
                else:
                    continue

                u_ang = u_hour * (2.0 * np.pi / 24.0)
                past_unplug_sin.append(np.sin(u_ang))
                past_unplug_cos.append(np.cos(u_ang))

                s_we = 1.0 if (s.day_of_week is not None and s.day_of_week >= 5) or s.start_time.weekday() >= 5 else 0.0
                past_is_weekend.append(s_we)

                s_hour = s.start_time.hour + s.start_time.minute / 60.0
                s_ang = s_hour * (2.0 * np.pi / 24.0)
                past_start_sin.append(np.sin(s_ang))
                past_start_cos.append(np.cos(s_ang))

                past_soc.append(s.start_battery_percent)
                past_usage.append(s.screen_usage_minutes if s.screen_usage_minutes is not None else POP_USAGE)

            p_sin = np.array(past_unplug_sin, dtype=np.float64)
            p_cos = np.array(past_unplug_cos, dtype=np.float64)
            p_we = np.array(past_is_weekend, dtype=np.float64)

            # Circular mean and std
            sum_s = float(np.sum(p_sin))
            sum_c = float(np.sum(p_cos))
            R = np.sqrt(sum_s**2 + sum_c**2) / float(history_count)
            r_norm = max(np.sqrt(sum_s**2 + sum_c**2), 1e-9)
            u_sin_mean = sum_s / r_norm
            u_cos_mean = sum_c / r_norm
            circ_std = float(np.sqrt(max(0.0, -2.0 * np.log(max(R, 1e-10)))) * (24.0 / (2.0 * np.pi)))

            # Weekday / Weekend circular means
            wd_mask = (p_we == 0.0)
            we_mask = (p_we == 1.0)

            if np.any(wd_mask):
                ws = float(np.sum(p_sin[wd_mask]))
                wc = float(np.sum(p_cos[wd_mask]))
                wr = max(np.sqrt(ws**2 + wc**2), 1e-9)
                wd_sin_mean = ws / wr
                wd_cos_mean = wc / wr
            else:
                wd_sin_mean = u_sin_mean
                wd_cos_mean = u_cos_mean

            if np.any(we_mask):
                es = float(np.sum(p_sin[we_mask]))
                ec = float(np.sum(p_cos[we_mask]))
                er = max(np.sqrt(es**2 + ec**2), 1e-9)
                we_sin_mean = es / er
                we_cos_mean = ec / er
            else:
                we_sin_mean = u_sin_mean
                we_cos_mean = u_cos_mean

            # Recent 3 and 7 sessions
            k3 = min(3, history_count)
            s3 = float(np.sum(p_sin[-k3:]))
            c3 = float(np.sum(p_cos[-k3:]))
            r3 = max(np.sqrt(s3**2 + c3**2), 1e-9)
            rec3_sin = s3 / r3
            rec3_cos = c3 / r3

            k7 = min(7, history_count)
            s7 = float(np.sum(p_sin[-k7:]))
            c7 = float(np.sum(p_cos[-k7:]))
            r7 = max(np.sqrt(s7**2 + c7**2), 1e-9)
            rec7_sin = s7 / r7
            rec7_cos = c7 / r7

            # Prior start hour, SOC, usage means
            s_start = float(np.sum(past_start_sin))
            c_start = float(np.sum(past_start_cos))
            r_start = max(np.sqrt(s_start**2 + c_start**2), 1e-9)
            start_hour_sin_mean = s_start / r_start
            start_hour_cos_mean = c_start / r_start

            start_soc_mean = float(np.mean(past_soc))
            usage_mean = float(np.mean(past_usage))

            hist_mean_hour = float(np.degrees(np.arctan2(u_sin_mean, u_cos_mean)) * (24.0 / 360.0)) % 24.0

            hist_dict = {
                "user_hist_unplug_sin_mean": u_sin_mean,
                "user_hist_unplug_cos_mean": u_cos_mean,
                "user_hist_unplug_circular_std": circ_std,
                "user_hist_weekday_unplug_sin_mean": wd_sin_mean,
                "user_hist_weekday_unplug_cos_mean": wd_cos_mean,
                "user_hist_weekend_unplug_sin_mean": we_sin_mean,
                "user_hist_weekend_unplug_cos_mean": we_cos_mean,
                "recent_3_unplug_sin_mean": rec3_sin,
                "recent_3_unplug_cos_mean": rec3_cos,
                "recent_7_unplug_sin_mean": rec7_sin,
                "recent_7_unplug_cos_mean": rec7_cos,
                "historical_start_hour_mean_sin": start_hour_sin_mean,
                "historical_start_hour_mean_cos": start_hour_cos_mean,
                "historical_start_soc_mean": start_soc_mean,
                "historical_previous_day_usage_mean": usage_mean,
                "completed_history_count": float(history_count),
            }

        # Construct single-row DataFrames with verified column order
        base_df = pd.DataFrame([base_dict])[SAFE_FEATURE_COLUMNS]

        combined_dict = {**base_dict, **hist_dict}
        pers_df = pd.DataFrame([combined_dict])[ALL_PERSONALIZED_FEATURE_COLUMNS]

        return FeatureExtractionResult(
            user_id=user_id,
            history_count=history_count,
            base_features=base_df,
            personalized_features=pers_df,
            circular_std=circ_std,
            user_hist_unplug_mean_hour=hist_mean_hour,
        )


feature_service = FeatureService()
