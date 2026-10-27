"""
Tests for the Personalized Charging Recommendation Engine.
Validates all 12 core functional requirements, safety guardrails,
and edge case scheduling logic.
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.schemas.recommendation import (
    RecommendationMode,
    PredictionSource,
    ConfidenceLevel,
    RecommendationRequest,
    ChargingRecommendationOutput,
    RecommendationPlan,
)
from app.services.recommendation_engine import (
    RecommendationEngine,
    RecommendationConfig,
)


@pytest.fixture
def engine():
    """Provides a fresh RecommendationEngine with standard configuration."""
    return RecommendationEngine()


# ------------------------------------------------------------------------------
# 1. Delayed Charging Calculation
# ------------------------------------------------------------------------------
def test_delayed_charging_calculation(engine):
    """
    Overnight session with plenty of slack:
    Plug: 22:00, Battery: 30%, Target: 80%, Standard Charger (30%/hr = 100 min)
    Predicted Unplug: 07:00 next day (9h = 540 min window).
    Buffer: 15 min.
    Start: 07:00 - 100 min - 15 min = 05:05.
    Finish: 06:45 (15 min buffer before unplug).
    Idle holding: 540 - 100 - 15 = 425 min.
    """
    plug_time = datetime(2026, 9, 10, 22, 0, 0, tzinfo=timezone.utc)
    pred_unplug = datetime(2026, 9, 11, 7, 0, 0, tzinfo=timezone.utc)

    req = RecommendationRequest(
        user_id=1,
        current_battery_percent=30.0,
        target_battery_percent=80.0,
        plug_time=plug_time,
        charger_type="standard",
        prediction_override=pred_unplug,
        confidence_score_override=0.90,
    )
    res = engine.generate_recommendation(req)

    assert res.mode == RecommendationMode.DELAYED_CHARGE.value
    assert res.estimated_charging_minutes == pytest.approx(100.0, abs=0.1)
    assert res.recommended_start_time == datetime(2026, 9, 11, 5, 5, 0, tzinfo=timezone.utc)
    assert res.estimated_finish_time == datetime(2026, 9, 11, 6, 45, 0, tzinfo=timezone.utc)
    assert res.idle_holding_minutes == pytest.approx(425.0, abs=0.1)
    assert res.confidence_level == ConfidenceLevel.HIGH.value


# ------------------------------------------------------------------------------
# 2. Already Above Target
# ------------------------------------------------------------------------------
def test_already_above_target(engine):
    """
    When current SOC >= target SOC, engine immediately indicates no charge needed.
    """
    plug_time = datetime(2026, 9, 10, 14, 0, 0, tzinfo=timezone.utc)
    pred_unplug = datetime(2026, 9, 10, 18, 0, 0, tzinfo=timezone.utc)

    req = RecommendationRequest(
        user_id=2,
        current_battery_percent=85.0,
        target_battery_percent=80.0,
        plug_time=plug_time,
        prediction_override=pred_unplug,
    )
    res = engine.generate_recommendation(req)

    assert res.mode == RecommendationMode.ALREADY_ABOVE_TARGET.value
    assert res.estimated_charging_minutes == 0.0
    assert res.recommended_start_time == plug_time
    assert res.estimated_finish_time == plug_time
    assert res.idle_holding_minutes == 0.0
    assert "already at or above" in res.reason.lower() or "meets or exceeds" in res.reason.lower()


# ------------------------------------------------------------------------------
# 3. Full Charge Preference (100% Target)
# ------------------------------------------------------------------------------
def test_full_charge_preference(engine):
    """
    User requests 100% full charge from 20% on standard charger (30%/hr).
    Needed: 80% -> 160 minutes.
    """
    plug_time = datetime(2026, 9, 10, 21, 0, 0, tzinfo=timezone.utc)
    pred_unplug = datetime(2026, 9, 11, 7, 0, 0, tzinfo=timezone.utc)

    req = RecommendationRequest(
        user_id=3,
        current_battery_percent=20.0,
        target_battery_percent=100.0,
        plug_time=plug_time,
        charger_type="standard",
        prediction_override=pred_unplug,
        confidence_score_override=0.88,
    )
    res = engine.generate_recommendation(req)

    assert res.target_soc == 100.0
    assert res.estimated_charging_minutes == pytest.approx(160.0, abs=0.1)
    # Start = 07:00 - 160 min - 15 min = 07:00 - 175 min = 04:05
    assert res.recommended_start_time == datetime(2026, 9, 11, 4, 5, 0, tzinfo=timezone.utc)
    assert res.estimated_finish_time == datetime(2026, 9, 11, 6, 45, 0, tzinfo=timezone.utc)
    assert res.mode == RecommendationMode.DELAYED_CHARGE.value


# ------------------------------------------------------------------------------
# 4. Insufficient Charging Time (CHARGE_NOW Fallback)
# ------------------------------------------------------------------------------
def test_insufficient_charging_time(engine):
    """
    Window is too short for delay:
    Plug: 13:00, Battery: 10%, Target: 80% (needs 70% / 30 = 140 min).
    Predicted unplug: 14:30 (90 min window).
    Since 90 min < 140 + 15 min, mode must be CHARGE_NOW starting immediately.
    """
    plug_time = datetime(2026, 9, 10, 13, 0, 0, tzinfo=timezone.utc)
    pred_unplug = datetime(2026, 9, 10, 14, 30, 0, tzinfo=timezone.utc)

    req = RecommendationRequest(
        user_id=4,
        current_battery_percent=10.0,
        target_battery_percent=80.0,
        plug_time=plug_time,
        charger_type="standard",
        prediction_override=pred_unplug,
        confidence_score_override=0.85,
    )
    res = engine.generate_recommendation(req)

    assert res.mode == RecommendationMode.CHARGE_NOW.value
    assert res.recommended_start_time == plug_time
    assert res.estimated_finish_time == plug_time + timedelta(minutes=140.0)
    assert res.idle_holding_minutes == 0.0


# ------------------------------------------------------------------------------
# 5. Low Confidence Conservative Behavior
# ------------------------------------------------------------------------------
def test_low_confidence_conservative_behavior(engine):
    """
    When confidence is low (score < 0.65 or circular_std >= 1.5),
    mode shifts to CONSERVATIVE_CHARGE and applies wider 30-minute buffer.
    """
    plug_time = datetime(2026, 9, 10, 22, 0, 0, tzinfo=timezone.utc)
    pred_unplug = datetime(2026, 9, 11, 7, 0, 0, tzinfo=timezone.utc)

    req = RecommendationRequest(
        user_id=5,
        current_battery_percent=30.0,
        target_battery_percent=80.0,
        plug_time=plug_time,
        charger_type="standard",
        prediction_override=pred_unplug,
        confidence_score_override=0.50,  # LOW confidence
    )
    res = engine.generate_recommendation(req, circular_std=1.8)

    assert res.mode == RecommendationMode.CONSERVATIVE_CHARGE.value
    assert res.confidence_level == ConfidenceLevel.LOW.value
    # Duration: 100 min, Conservative buffer: 30 min -> total 130 min before 07:00 -> 04:50
    assert res.recommended_start_time == datetime(2026, 9, 11, 4, 50, 0, tzinfo=timezone.utc)
    assert res.estimated_finish_time == datetime(2026, 9, 11, 6, 30, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------------------------
# 6. Temperature Warning
# ------------------------------------------------------------------------------
def test_temperature_warning(engine):
    """
    When battery temperature >= 35.0°C, engine generates a thermal warning
    and advises ambient cooling.
    """
    plug_time = datetime(2026, 9, 10, 22, 0, 0, tzinfo=timezone.utc)
    pred_unplug = datetime(2026, 9, 11, 7, 0, 0, tzinfo=timezone.utc)

    req = RecommendationRequest(
        user_id=6,
        current_battery_percent=40.0,
        target_battery_percent=80.0,
        plug_time=plug_time,
        current_temperature=38.5,
        prediction_override=pred_unplug,
        confidence_score_override=0.85,
    )
    res = engine.generate_recommendation(req)

    assert len(res.warnings) >= 1
    assert any("temperature" in w.lower() for w in res.warnings)
    assert "38.5°C" in res.warnings[0]
    assert "ambient cooling" in res.recommendation_message.lower() or "temperature" in res.recommendation_message.lower()


# ------------------------------------------------------------------------------
# 7. Midnight Crossing
# ------------------------------------------------------------------------------
def test_midnight_crossing(engine):
    """
    Plug at 23:45 on Day 1, unplug at 07:15 on Day 2.
    Ensures date increments properly, start and finish are on Day 2,
    and no day-wrap or negative time bugs occur.
    """
    plug_time = datetime(2026, 9, 10, 23, 45, 0, tzinfo=timezone.utc)
    pred_unplug = datetime(2026, 9, 11, 7, 15, 0, tzinfo=timezone.utc)

    req = RecommendationRequest(
        user_id=7,
        current_battery_percent=50.0,
        target_battery_percent=80.0,
        plug_time=plug_time,
        charger_type="standard",
        prediction_override=pred_unplug,
        confidence_score_override=0.85,
    )
    res = engine.generate_recommendation(req)

    # 30% needed / 30%/hr = 60 min duration + 15 min buffer = 75 min before 07:15 -> 06:00
    assert res.recommended_start_time.date() == datetime(2026, 9, 11).date()
    assert res.recommended_start_time == datetime(2026, 9, 11, 6, 0, 0, tzinfo=timezone.utc)
    assert res.estimated_finish_time == datetime(2026, 9, 11, 7, 0, 0, tzinfo=timezone.utc)
    assert res.recommended_start_time > plug_time


# ------------------------------------------------------------------------------
# 8. Rate Validation
# ------------------------------------------------------------------------------
def test_rate_validation(engine):
    """
    Verifies default charger type rates, custom overrides, and error on non-positive rate.
    """
    assert engine.get_charging_rate("slow") == 12.0
    assert engine.get_charging_rate("standard") == 30.0
    assert engine.get_charging_rate("fast") == 60.0
    assert engine.get_charging_rate("unknown_type") == 30.0  # Safe fallback

    # Custom override
    assert engine.get_charging_rate("standard", override_rate=45.0) == 45.0

    # Non-positive rate raises ValueError
    with pytest.raises(ValueError, match="strictly positive"):
        engine.get_charging_rate("standard", override_rate=0.0)

    with pytest.raises(ValueError, match="strictly positive"):
        engine.get_charging_rate("standard", override_rate=-10.0)


# ------------------------------------------------------------------------------
# 9. Invalid SOC Values
# ------------------------------------------------------------------------------
def test_invalid_soc_values(engine):
    """
    current_battery_percent outside [0, 100] raises ValueError.
    """
    with pytest.raises(ValueError, match="Invalid current SOC"):
        engine.validate_soc(-5.0, 80.0)

    with pytest.raises(ValueError, match="Invalid current SOC"):
        engine.validate_soc(105.0, 80.0)


# ------------------------------------------------------------------------------
# 10. Target Constraints
# ------------------------------------------------------------------------------
def test_target_constraints(engine):
    """
    target_battery_percent below minimum (70%) or above 100% raises ValueError.
    """
    with pytest.raises(ValueError, match="Invalid target SOC"):
        engine.validate_soc(50.0, 65.0)  # Below 70% min

    with pytest.raises(ValueError, match="Invalid target SOC"):
        engine.validate_soc(50.0, 105.0)  # Above 100%


# ------------------------------------------------------------------------------
# 11. Non-Negative Duration
# ------------------------------------------------------------------------------
def test_non_negative_duration(engine):
    """
    Estimated duration must be strictly non-negative across edge cases.
    """
    plug_time = datetime(2026, 9, 10, 22, 0, 0, tzinfo=timezone.utc)
    pred_unplug = datetime(2026, 9, 11, 7, 0, 0, tzinfo=timezone.utc)

    # Exactly at target
    req_at_target = RecommendationRequest(
        user_id=11,
        current_battery_percent=80.0,
        target_battery_percent=80.0,
        plug_time=plug_time,
        prediction_override=pred_unplug,
    )
    res1 = engine.generate_recommendation(req_at_target)
    assert res1.estimated_charging_minutes >= 0.0
    assert res1.estimated_charging_minutes == 0.0

    # Above target
    req_above_target = RecommendationRequest(
        user_id=11,
        current_battery_percent=95.0,
        target_battery_percent=80.0,
        plug_time=plug_time,
        prediction_override=pred_unplug,
    )
    res2 = engine.generate_recommendation(req_above_target)
    assert res2.estimated_charging_minutes >= 0.0
    assert res2.estimated_charging_minutes == 0.0


# ------------------------------------------------------------------------------
# 12. Human-Readable Message Generation
# ------------------------------------------------------------------------------
def test_human_readable_message_generation(engine):
    """
    Verifies that the recommendation message is clear, contains explicit HH:MM times,
    target SOC percentage, and does not claim unverified chemical lifespan elongation.
    """
    plug_time = datetime(2026, 9, 10, 22, 0, 0, tzinfo=timezone.utc)
    pred_unplug = datetime(2026, 9, 11, 7, 0, 0, tzinfo=timezone.utc)

    req = RecommendationRequest(
        user_id=12,
        current_battery_percent=30.0,
        target_battery_percent=80.0,
        plug_time=plug_time,
        prediction_override=pred_unplug,
        confidence_score_override=0.88,
    )
    res = engine.generate_recommendation(req)

    msg = res.recommendation_message
    assert "80%" in msg
    assert ":" in msg  # Contains clock time like 05:05 or 06:45
    # Does NOT make unsubstantiated marketing claims
    assert "double" not in msg.lower()
    assert "doubles" not in msg.lower()
    assert "triple" not in msg.lower()


# ------------------------------------------------------------------------------
# 13. Cold-Start and Personalization Source Determination
# ------------------------------------------------------------------------------
def test_prediction_source_history_tiers(engine):
    """
    Tests prediction source metadata based on completed history counts.
    """
    plug_time = datetime(2026, 9, 10, 22, 0, 0, tzinfo=timezone.utc)

    # With 0 history -> RULE_BASED or GLOBAL_BASELINE
    dt, conf, source = engine.predict_unplug_time(1, plug_time, 40.0, history_count=0)
    assert source in [PredictionSource.GLOBAL_BASELINE.value, PredictionSource.RULE_BASED.value]


# ------------------------------------------------------------------------------
# 14. Legacy Plan Adapter Compatibility
# ------------------------------------------------------------------------------
def test_legacy_plan_adapter(engine):
    """
    Verifies that RecommendationEngine.to_recommendation_plan produces
    a valid RecommendationPlan conforming to existing API dashboard schemas.
    """
    plug_time = datetime(2026, 9, 10, 22, 0, 0, tzinfo=timezone.utc)
    pred_unplug = datetime(2026, 9, 11, 7, 0, 0, tzinfo=timezone.utc)

    req = RecommendationRequest(
        user_id=14,
        current_battery_percent=30.0,
        target_battery_percent=80.0,
        plug_time=plug_time,
        prediction_override=pred_unplug,
        confidence_score_override=0.90,
    )
    out = engine.generate_recommendation(req)
    plan = engine.to_recommendation_plan(out)

    assert isinstance(plan, RecommendationPlan)
    assert plan.mode == "optimized_delayed"
    assert plan.hold_at_pct == 80.0
    assert plan.phase_2_topoff_start is not None
    assert plan.estimated_ready_time is not None


# ------------------------------------------------------------------------------
# 15. Future-Time Rollover & Non-Past Scheduling
# ------------------------------------------------------------------------------
def test_unplug_time_strictly_future_rollover(engine):
    """
    Ensures candidate unplug time is strictly in the future relative to plug_time.
    When plugged in at 22:30 and predicted unplug hour is 07:15,
    unplug time must roll over to next calendar day (> plug_time).
    """
    plug_time = datetime(2026, 9, 10, 22, 30, 0, tzinfo=timezone.utc)
    # Provide candidate earlier on the same calendar day
    candidate_same_day = datetime(2026, 9, 10, 7, 15, 0, tzinfo=timezone.utc)

    req = RecommendationRequest(
        user_id=15,
        current_battery_percent=40.0,
        target_battery_percent=80.0,
        plug_time=plug_time,
        prediction_override=candidate_same_day,
    )
    res = engine.generate_recommendation(req)

    assert res.predicted_unplug_time > plug_time
    assert res.predicted_unplug_time.date() == datetime(2026, 9, 11).date()
    assert res.predicted_unplug_time == datetime(2026, 9, 11, 7, 15, 0, tzinfo=timezone.utc)


def test_recommended_start_never_earlier_than_plug_time(engine):
    """
    Guarantees that recommended_start_time is never in the past relative to plug_time,
    even under tight windows, zero slack, or low battery with delayed charge.
    """
    # Case A: Tight window -> CHARGE_NOW at plug_time
    plug_time = datetime(2026, 9, 10, 18, 0, 0, tzinfo=timezone.utc)
    pred_unplug = datetime(2026, 9, 10, 19, 0, 0, tzinfo=timezone.utc)
    req = RecommendationRequest(
        user_id=16,
        current_battery_percent=10.0,
        target_battery_percent=80.0,
        plug_time=plug_time,
        prediction_override=pred_unplug,
    )
    res = engine.generate_recommendation(req)
    assert res.recommended_start_time >= plug_time
    assert res.mode == RecommendationMode.CHARGE_NOW.value

    # Case B: Multi-day past candidate -> rolls forward into future
    past_candidate = datetime(2026, 9, 8, 14, 0, 0, tzinfo=timezone.utc)
    req_past = RecommendationRequest(
        user_id=16,
        current_battery_percent=50.0,
        target_battery_percent=80.0,
        plug_time=plug_time,
        prediction_override=past_candidate,
    )
    res_past = engine.generate_recommendation(req_past)
    assert res_past.predicted_unplug_time > plug_time
    assert res_past.recommended_start_time >= plug_time
