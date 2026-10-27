from datetime import datetime, timedelta, timezone
from typing import Tuple
from app.core.config import settings
from app.schemas.recommendation import RecommendationPlan


class ChargingOptimizerService:
    """
    Computes battery-health preserving charging schedules based on
    predicted unplug time and battery degradation mitigation rules.
    """

    # Estimated charging rates:
    # 0% -> 80%: ~1.0% per minute (Active Fast/Standard charging)
    # 80% -> 100%: ~0.5% per minute (Constant Voltage / Tapered charging)
    MINUTES_PER_PCT_FAST = 1.0
    MINUTES_PER_PCT_TAPERING = 2.0

    def __init__(self, predictor=None):
        self.predictor = predictor

    def predict_unplug(self, user_id: str, plug_time: datetime) -> Tuple[datetime, float]:
        """
        Queries the ML model predictor for unplug time estimation.
        Falls back to rule-based diurnal heuristics if ML model is unavailable.
        """
        if self.predictor is not None and hasattr(self.predictor, "predict"):
            try:
                res = self.predictor.predict(user_id=user_id, plug_time=plug_time)
                if isinstance(res, tuple):
                    predicted_unplug, confidence = res
                elif hasattr(res, "predicted_unplug_datetime"):
                    predicted_unplug = res.predicted_unplug_datetime
                    confidence = res.confidence_score
                else:
                    predicted_unplug, confidence = res, 0.75

                while predicted_unplug <= plug_time:
                    predicted_unplug += timedelta(days=1)
                return predicted_unplug, confidence
            except Exception:
                pass

        # Rule-based fallback heuristic:
        # If plugged in late evening (>= 21:00 or < 05:00), assume overnight charging until ~07:30 AM
        hour = plug_time.hour
        tz = plug_time.tzinfo or timezone.utc
        if hour >= 21 or hour < 5:
            target_date = plug_time.date() if hour < 5 else (plug_time + timedelta(days=1)).date()
            predicted_unplug = datetime(
                year=target_date.year,
                month=target_date.month,
                day=target_date.day,
                hour=7,
                minute=30,
                tzinfo=tz,
            )
            confidence = 0.75
        else:
            # Daytime quick top-up: assume ~2 hours session
            predicted_unplug = plug_time + timedelta(hours=2)
            confidence = 0.60

        while predicted_unplug <= plug_time:
            predicted_unplug += timedelta(days=1)

        return predicted_unplug, confidence

    def generate_charging_plan(
        self,
        user_id: str,
        plug_time: datetime,
        start_battery_pct: float,
        target_battery_pct: float = 100.0,
    ) -> Tuple[datetime, RecommendationPlan]:
        """
        Generates optimal phases:
        1. Fast Charge up to 80% (or target if target <= 80%)
        2. Protection Hold at 80%
        3. Resume Top-off to target before predicted unplug
        """
        predicted_unplug, confidence = self.predict_unplug(user_id, plug_time)
        hold_pct = min(settings.BATTERY_HEALTH_MAX_LIMIT_PCT, target_battery_pct)

        # 1. Calculate time needed to reach hold_pct (e.g. 80%)
        if start_battery_pct < hold_pct:
            pct_needed_phase1 = hold_pct - start_battery_pct
            minutes_phase1 = pct_needed_phase1 * self.MINUTES_PER_PCT_FAST
        else:
            minutes_phase1 = 0.0

        phase_1_fast_until = plug_time + timedelta(minutes=minutes_phase1)

        # 2. Calculate time needed for Phase 2 top-off (80% -> target)
        if target_battery_pct > hold_pct:
            pct_needed_topoff = target_battery_pct - hold_pct
            minutes_topoff = pct_needed_topoff * self.MINUTES_PER_PCT_TAPERING
        else:
            minutes_topoff = 0.0

        # Buffer before unplug to guarantee device is ready
        buffer_minutes = settings.FALLBACK_BUFFER_MINUTES
        phase_2_topoff_start = predicted_unplug - timedelta(minutes=minutes_topoff + buffer_minutes)
        estimated_ready_time = predicted_unplug - timedelta(minutes=buffer_minutes)

        # If unplug happens too soon or top-off starts in the past, fall back to direct continuous charging
        if phase_2_topoff_start <= phase_1_fast_until or phase_2_topoff_start <= plug_time:
            mode = "standard_direct"
            phase_1_fast_until = None
            phase_2_topoff_start = None
            total_minutes = (
                max(0.0, hold_pct - start_battery_pct) * self.MINUTES_PER_PCT_FAST
                + max(0.0, target_battery_pct - max(start_battery_pct, hold_pct)) * self.MINUTES_PER_PCT_TAPERING
            )
            estimated_ready_time = plug_time + timedelta(minutes=total_minutes)
            rec_message = f"Direct continuous charging recommended to reach {target_battery_pct:.0f}% before predicted unplug."
        else:
            mode = "optimized_delayed"
            rec_message = (
                f"Optimized schedule: Fast charge to {hold_pct:.0f}%, hold until "
                f"{phase_2_topoff_start.strftime('%H:%M')}, top off to {target_battery_pct:.0f}% by "
                f"{estimated_ready_time.strftime('%H:%M')}."
            )

        plan = RecommendationPlan(
            mode=mode,
            phase_1_fast_charge_until=phase_1_fast_until,
            hold_at_pct=hold_pct,
            phase_2_topoff_start=phase_2_topoff_start,
            estimated_ready_time=estimated_ready_time,
            confidence_score=round(confidence, 2),
            recommendation_message=rec_message,
        )

        return predicted_unplug, plan


# Default singleton instance
optimizer_service = ChargingOptimizerService()
