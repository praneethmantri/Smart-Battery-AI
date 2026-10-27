"""
Smart Battery AI - Personalized Charging Recommendation Engine
=============================================================
Calculates personalized, battery-health preserving charging schedules based on
ML predicted unplug time, historical user behavior, battery state of charge (SOC),
and thermal constraints.

Advisory & Scheduling ONLY - Does NOT directly control hardware relays or OS charging switches.
Avoids unverified lifespan claims; focuses strictly on measurable proxy metrics
such as reduction of early-completion high-SOC idle stress.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Tuple, Any
import logging

from app.schemas.recommendation import (
    RecommendationMode,
    PredictionSource,
    ConfidenceLevel,
    RecommendationRequest,
    ChargingRecommendationOutput,
    RecommendationPlan,
)

logger = logging.getLogger(__name__)


@dataclass
class RecommendationConfig:
    """Configurable algorithmic parameters for recommendation scheduling."""
    default_target_soc: float = 80.0
    full_charge_target: float = 100.0
    minimum_target_soc: float = 70.0
    high_temperature_warning_threshold: float = 35.0  # Celsius
    charging_buffer_minutes: float = 15.0  # Safety buffer in minutes
    conservative_buffer_minutes: float = 30.0  # Extended buffer for irregular/low-confidence users
    minimum_history_for_personalization: int = 3
    full_personalization_history: int = 7
    default_charging_rates: Dict[str, float] = field(default_factory=lambda: {
        "slow": 12.0,      # 12.0% per hour (0.20% per min)
        "standard": 30.0,  # 30.0% per hour (0.50% per min)
        "fast": 60.0,      # 60.0% per hour (1.00% per min)
    })
    low_confidence_threshold: float = 0.65
    high_variance_threshold_hours: float = 1.5


class RecommendationEngine:
    """
    Core service that transforms unplug-time predictions into actionable,
    battery-health conscious charging recommendations.
    """

    def __init__(
        self,
        config: Optional[RecommendationConfig] = None,
        predictor: Optional[Any] = None,
    ):
        self.config = config or RecommendationConfig()
        self.predictor = predictor

    def get_charging_rate(
        self,
        charger_type: Optional[str] = "standard",
        override_rate: Optional[float] = None,
    ) -> float:
        """
        Determines the active charging rate in % SOC per hour.
        Validates that rate is strictly positive.
        """
        if override_rate is not None:
            if override_rate <= 0.0:
                raise ValueError(f"Charging rate must be strictly positive, got: {override_rate}")
            return float(override_rate)

        norm_type = (charger_type or "standard").strip().lower()
        if norm_type in self.config.default_charging_rates:
            return float(self.config.default_charging_rates[norm_type])

        # Default to standard if unrecognized
        return float(self.config.default_charging_rates.get("standard", 30.0))

    def validate_soc(self, current_soc: float, target_soc: float) -> None:
        """
        Validates that SOC values conform to physical and policy limits.
        Raises ValueError if outside acceptable boundaries.
        """
        if not (0.0 <= current_soc <= 100.0):
            raise ValueError(
                f"Invalid current SOC: {current_soc}%. Must be between 0.0% and 100.0%."
            )
        if not (self.config.minimum_target_soc <= target_soc <= 100.0):
            raise ValueError(
                f"Invalid target SOC: {target_soc}%. Must be between "
                f"{self.config.minimum_target_soc}% and 100.0%."
            )

    def classify_confidence(
        self,
        confidence_score: float,
        circular_std: Optional[float] = None,
    ) -> str:
        """
        Categorizes prediction confidence into HIGH, MEDIUM, or LOW.
        High schedule variance forces LOW confidence to trigger conservative guardrails.
        """
        if circular_std is not None and circular_std >= self.config.high_variance_threshold_hours:
            return ConfidenceLevel.LOW.value

        if confidence_score >= 0.80:
            return ConfidenceLevel.HIGH.value
        elif confidence_score >= self.config.low_confidence_threshold:
            return ConfidenceLevel.MEDIUM.value
        else:
            return ConfidenceLevel.LOW.value

    def predict_unplug_time(
        self,
        user_id: int,
        plug_time: datetime,
        current_soc: float,
        charger_type: str = "standard",
        history_count: Optional[int] = None,
    ) -> Tuple[datetime, float, str]:
        """
        Queries predictor if available, falling back to rule-based diurnal heuristics.
        Returns: (predicted_unplug_time, confidence_score, prediction_source)
        """
        if self.predictor is not None and hasattr(self.predictor, "predict"):
            try:
                pred_dt, conf = self.predictor.predict(
                    user_id=str(user_id),
                    plug_time=plug_time,
                    start_battery_pct=current_soc,
                    charger_type=charger_type,
                )
                if history_count is None:
                    source = PredictionSource.GLOBAL_BASELINE.value
                elif history_count < self.config.minimum_history_for_personalization:
                    source = PredictionSource.GLOBAL_BASELINE.value
                elif history_count < self.config.full_personalization_history:
                    source = PredictionSource.BLENDED.value
                else:
                    source = PredictionSource.PERSONALIZED.value

                return pred_dt, float(conf), source
            except Exception as e:
                logger.warning("Predictor query failed, using rule-based fallback: %s", str(e))

        # Diurnal rule-based fallback
        hour = plug_time.hour
        if hour >= 21 or hour < 5:
            target_date = plug_time.date() if hour < 5 else (plug_time + timedelta(days=1)).date()
            pred_dt = datetime(
                year=target_date.year,
                month=target_date.month,
                day=target_date.day,
                hour=7,
                minute=30,
                tzinfo=plug_time.tzinfo or timezone.utc,
            )
            conf = 0.75
        else:
            pred_dt = plug_time + timedelta(hours=2)
            conf = 0.60

        while pred_dt <= plug_time:
            pred_dt += timedelta(days=1)

        return pred_dt, conf, PredictionSource.RULE_BASED.value

    def generate_recommendation(
        self,
        request: RecommendationRequest,
        history_count: Optional[int] = None,
        circular_std: Optional[float] = None,
        is_irregular: bool = False,
    ) -> ChargingRecommendationOutput:
        """
        Generates a personalized charging recommendation with detailed timing,
        mode classification, and safety warnings.
        """
        target_soc = (
            request.target_battery_percent
            if request.target_battery_percent is not None
            else self.config.default_target_soc
        )
        current_soc = request.current_battery_percent

        # 1. Validate SOC bounds
        self.validate_soc(current_soc, target_soc)

        # 2. Resolve plug time (normalize to UTC if naive)
        plug_time = request.plug_time or datetime.now(timezone.utc)
        if plug_time.tzinfo is None:
            plug_time = plug_time.replace(tzinfo=timezone.utc)

        # 3. Thermal Check
        warnings: List[str] = []
        if request.current_temperature is not None and request.current_temperature >= self.config.high_temperature_warning_threshold:
            warnings.append(
                f"Elevated battery temperature detected ({request.current_temperature:.1f}°C >= "
                f"{self.config.high_temperature_warning_threshold:.1f}°C). Charging at high temperatures accelerates "
                f"electrolyte and SEI layer degradation. Ambient cooling is advised before rapid charging."
            )

        # 4. Resolve Predicted Unplug Time & Confidence
        if request.prediction_override is not None:
            predicted_unplug = request.prediction_override
            if predicted_unplug.tzinfo is None:
                predicted_unplug = predicted_unplug.replace(tzinfo=plug_time.tzinfo)
            confidence_score = (
                request.confidence_score_override
                if request.confidence_score_override is not None
                else 0.85
            )
            source = PredictionSource.GLOBAL_BASELINE.value
        else:
            predicted_unplug, confidence_score, source = self.predict_unplug_time(
                user_id=request.user_id,
                plug_time=plug_time,
                current_soc=current_soc,
                charger_type=request.charger_type or "standard",
                history_count=history_count,
            )

        # Ensure timezone consistency
        if predicted_unplug.tzinfo is None:
            predicted_unplug = predicted_unplug.replace(tzinfo=plug_time.tzinfo)

        # Handle midnight rollover if candidate unplug occurs earlier on same calendar day
        while predicted_unplug <= plug_time:
            predicted_unplug += timedelta(days=1)

        # 5. Classify Confidence & Determine Safety Margin
        confidence_level = self.classify_confidence(confidence_score, circular_std=circular_std)
        conservative_trigger = (
            confidence_level == ConfidenceLevel.LOW.value
            or is_irregular
            or (circular_std is not None and circular_std >= self.config.high_variance_threshold_hours)
        )

        buffer_minutes = (
            self.config.conservative_buffer_minutes
            if conservative_trigger
            else self.config.charging_buffer_minutes
        )

        # 6. Effective Charging Rate
        rate_pct_per_hr = self.get_charging_rate(request.charger_type)

        # 7. Core Scheduling Algorithm
        if current_soc >= target_soc:
            # Mode: ALREADY_ABOVE_TARGET
            mode = RecommendationMode.ALREADY_ABOVE_TARGET.value
            duration_minutes = 0.0
            recommended_start = plug_time
            estimated_finish = plug_time
            idle_holding_minutes = 0.0
            reason = (
                f"Current battery level ({current_soc:.0f}%) is already at or above "
                f"the target SOC ({target_soc:.0f}%). No active charging is necessary."
            )
            msg = (
                f"Battery is currently at {current_soc:.0f}%, meeting your target of {target_soc:.0f}%. "
                f"Device is ready for use."
            )
        else:
            needed_pct = target_soc - current_soc
            duration_hours = needed_pct / rate_pct_per_hr
            duration_minutes = round(max(0.0, duration_hours * 60.0), 2)

            available_window_minutes = (predicted_unplug - plug_time).total_seconds() / 60.0
            slack_minutes = available_window_minutes - (duration_minutes + buffer_minutes)

            if slack_minutes > 0.0:
                # Ample window: Schedule delayed charging
                recommended_start = predicted_unplug - timedelta(minutes=(duration_minutes + buffer_minutes))
                if recommended_start < plug_time:
                    recommended_start = plug_time
                estimated_finish = recommended_start + timedelta(minutes=duration_minutes)
                idle_holding_minutes = round(slack_minutes, 2)

                if conservative_trigger:
                    mode = RecommendationMode.CONSERVATIVE_CHARGE.value
                    reason = (
                        f"Schedule exhibits irregular patterns or low confidence ({confidence_score:.2f}). "
                        f"Applied extended {buffer_minutes:.0f}-minute readiness buffer before predicted unplug."
                    )
                    msg = (
                        f"Conservative schedule: Delay charging until {recommended_start.strftime('%H:%M')}. "
                        f"Target {target_soc:.0f}% will be reached by {estimated_finish.strftime('%H:%M')} "
                        f"({buffer_minutes:.0f} min before predicted unplug at {predicted_unplug.strftime('%H:%M')})."
                    )
                else:
                    mode = RecommendationMode.DELAYED_CHARGE.value
                    reason = (
                        f"Available window ({available_window_minutes:.0f} min) allows postponing charge start by {slack_minutes:.0f} min, "
                        f"minimizing high-SOC idle stress before predicted unplug at {predicted_unplug.strftime('%H:%M')}."
                    )
                    msg = (
                        f"Optimized schedule: Delay charging until {recommended_start.strftime('%H:%M')}. "
                        f"Battery will reach target {target_soc:.0f}% by {estimated_finish.strftime('%H:%M')} "
                        f"({buffer_minutes:.0f} min before unplug)."
                    )
            else:
                # Tight window: Start immediately
                recommended_start = plug_time
                estimated_finish = plug_time + timedelta(minutes=duration_minutes)
                idle_holding_minutes = 0.0

                if conservative_trigger:
                    mode = RecommendationMode.CONSERVATIVE_CHARGE.value
                    reason = (
                        f"Low confidence ({confidence_score:.2f}) and tight window ({available_window_minutes:.0f} min vs "
                        f"{duration_minutes:.0f} min required) necessitate immediate charging."
                    )
                    msg = (
                        f"Start charging immediately: Continuous charging to {target_soc:.0f}% recommended "
                        f"to guarantee battery readiness by {estimated_finish.strftime('%H:%M')}."
                    )
                else:
                    mode = RecommendationMode.CHARGE_NOW.value
                    reason = (
                        f"Estimated charging duration ({duration_minutes:.0f} min) plus buffer ({buffer_minutes:.0f} min) "
                        f"exceeds available window ({available_window_minutes:.0f} min). Immediate charging required."
                    )
                    msg = (
                        f"Start charging now. Expected to reach target {target_soc:.0f}% by "
                        f"{estimated_finish.strftime('%H:%M')}."
                    )

        # Thermal advisory suffix
        if warnings and mode != RecommendationMode.ALREADY_ABOVE_TARGET.value:
            msg += f" Note: Battery temperature is {request.current_temperature:.1f}°C; ambient cooling recommended."

        return ChargingRecommendationOutput(
            user_id=request.user_id,
            prediction_source=source,
            predicted_unplug_time=predicted_unplug,
            current_soc=current_soc,
            target_soc=target_soc,
            recommended_start_time=recommended_start,
            estimated_finish_time=estimated_finish,
            estimated_charging_minutes=duration_minutes,
            confidence_level=confidence_level,
            confidence_score=round(confidence_score, 2),
            mode=mode,
            recommendation_message=msg,
            reason=reason,
            warnings=warnings,
            charging_rate_pct_per_hr=rate_pct_per_hr,
            idle_holding_minutes=idle_holding_minutes,
        )

    def to_recommendation_plan(self, output: ChargingRecommendationOutput) -> RecommendationPlan:
        """
        Maps a ChargingRecommendationOutput to the legacy RecommendationPlan schema
        used by dashboard endpoints.
        """
        legacy_mode = (
            "optimized_delayed"
            if output.mode in [RecommendationMode.DELAYED_CHARGE.value, RecommendationMode.CONSERVATIVE_CHARGE.value]
            else "standard_direct"
        )
        return RecommendationPlan(
            mode=legacy_mode,
            phase_1_fast_charge_until=output.estimated_finish_time if legacy_mode == "standard_direct" else None,
            hold_at_pct=output.target_soc,
            phase_2_topoff_start=output.recommended_start_time if legacy_mode == "optimized_delayed" else None,
            estimated_ready_time=output.estimated_finish_time,
            confidence_score=output.confidence_score,
            recommendation_message=output.recommendation_message,
        )


# Global default instance
recommendation_engine = RecommendationEngine()
