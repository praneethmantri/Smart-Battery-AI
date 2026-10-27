from datetime import datetime, timezone
from app.services.optimizer import ChargingOptimizerService


def test_optimizer_overnight_plan():
    optimizer = ChargingOptimizerService()
    # Plugged in at 23:00 (11 PM) with 20% battery
    plug_time = datetime(2026, 9, 10, 23, 0, 0, tzinfo=timezone.utc)
    predicted_unplug, plan = optimizer.generate_charging_plan(
        user_id="user_test",
        plug_time=plug_time,
        start_battery_pct=20.0,
        target_battery_pct=100.0,
    )

    assert plan.mode == "optimized_delayed"
    assert plan.hold_at_pct == 80.0
    assert plan.phase_1_fast_charge_until is not None
    assert plan.phase_2_topoff_start is not None
    assert plan.phase_2_topoff_start > plan.phase_1_fast_charge_until
    assert predicted_unplug.hour == 7


def test_optimizer_short_session_fallback():
    optimizer = ChargingOptimizerService()
    # Plugged in at 14:00 (daytime short window, heuristic duration ~2 hours)
    plug_time = datetime(2026, 9, 10, 14, 0, 0, tzinfo=timezone.utc)
    predicted_unplug, plan = optimizer.generate_charging_plan(
        user_id="user_test",
        plug_time=plug_time,
        start_battery_pct=10.0,
        target_battery_pct=100.0,
    )

    # In a 2 hour window, reaching 80% takes 70 mins and topping off takes 40 mins + 30 mins buffer = 140 mins > 120 mins
    # Thus it should fall back to standard_direct
    assert plan.mode == "standard_direct"
