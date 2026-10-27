import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db.base import Base
from app.models.user import User
from app.models.charging_session import ChargingSession
from app.models.telemetry_sample import TelemetrySample
from app.services.telemetry_service import WindowsTelemetryService
from app.services.feature_service import feature_service
from app.services.ml_service import ml_service
from app.main import app


@pytest.fixture
def test_db(db_session):
    """Ensure test user 1 exists in the conftest in-memory database session."""
    user = db_session.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, name="Test Windows User", email="test.user@windows.local")
        db_session.add(user)
        db_session.commit()
    return db_session


# =====================================================================
# 1. Plug Detection Test
# =====================================================================
def test_plug_detection_starts_real_session(test_db):
    """Verifies unplugged -> plugged transition creates a REAL_WINDOWS charging session."""
    collector = WindowsTelemetryService(target_user_id=1, poll_interval_seconds=120)

    # First poll: unplugged
    with patch("app.services.device_battery_service.device_battery_service.get_battery_status") as mock_batt, \
         patch.object(collector, "get_system_idle_seconds", return_value=5.0):
        mock_batt.return_value = {
            "available": True,
            "battery_percent": 42.0,
            "is_plugged_in": False,
            "seconds_left": 3600,
            "source": "WINDOWS_SYSTEM",
        }
        res1 = collector.poll_once(db=test_db)
        assert res1["success"] is True
        assert collector.active_session_id is None

        # Second poll: plugged in
        mock_batt.return_value = {
            "available": True,
            "battery_percent": 43.0,
            "is_plugged_in": True,
            "seconds_left": None,
            "source": "WINDOWS_SYSTEM",
        }
        res2 = collector.poll_once(db=test_db)
        assert res2["success"] is True
        assert res2["transition_event"] == "PLUG_DETECTED_SESSION_STARTED"
        assert collector.active_session_id is not None

        # Verify database record
        session = test_db.query(ChargingSession).filter(ChargingSession.id == collector.active_session_id).first()
        assert session is not None
        assert session.data_source == "REAL_WINDOWS"
        assert session.start_battery_percent == 43.0
        assert session.end_time is None


# =====================================================================
# 2. Unplug Detection Test
# =====================================================================
def test_unplug_detection_completes_session(test_db):
    """Verifies plugged -> unplugged transition finalizes the active session."""
    collector = WindowsTelemetryService(target_user_id=1, poll_interval_seconds=120)
    now = datetime.now(timezone.utc) - timedelta(minutes=45)

    # Seed an active session
    sess = ChargingSession(
        user_id=1,
        start_time=now,
        start_battery_percent=40.0,
        end_time=None,
        data_source="REAL_WINDOWS",
    )
    test_db.add(sess)
    test_db.commit()
    test_db.refresh(sess)

    collector.active_session_id = sess.id
    collector.session_start_time = now
    collector.last_plugged_state = True
    collector.session_active_seconds = 1800.0  # 30 mins active
    collector.session_idle_seconds = 900.0    # 15 mins idle

    # Poll with unplugged state
    with patch("app.services.device_battery_service.device_battery_service.get_battery_status") as mock_batt, \
         patch.object(collector, "get_system_idle_seconds", return_value=10.0):
        mock_batt.return_value = {
            "available": True,
            "battery_percent": 82.0,
            "is_plugged_in": False,
            "seconds_left": 5000,
            "source": "WINDOWS_SYSTEM",
        }
        res = collector.poll_once(db=test_db)
        assert res["success"] is True
        assert res["transition_event"] == "UNPLUG_DETECTED_SESSION_COMPLETED"
        assert collector.active_session_id is None

        # Check DB session completed
        updated = test_db.query(ChargingSession).filter(ChargingSession.id == sess.id).first()
        assert updated.end_time is not None
        assert updated.end_battery_percent == 82.0
        assert updated.charging_duration_minutes >= 44.0
        assert updated.screen_usage_minutes == 30.0
        assert updated.idle_usage_minutes == 15.0


# =====================================================================
# 3. Duplicate Prevention Test
# =====================================================================
def test_duplicate_prevention_on_repeated_polls(test_db):
    """Verifies repeated polls while plugged in DO NOT create duplicate sessions."""
    collector = WindowsTelemetryService(target_user_id=1, poll_interval_seconds=120)

    with patch("app.services.device_battery_service.device_battery_service.get_battery_status") as mock_batt, \
         patch.object(collector, "get_system_idle_seconds", return_value=2.0):
        mock_batt.return_value = {
            "available": True,
            "battery_percent": 50.0,
            "is_plugged_in": True,
            "seconds_left": None,
            "source": "WINDOWS_SYSTEM",
        }

        # First poll: starts session
        collector.last_plugged_state = False
        res1 = collector.poll_once(db=test_db)
        initial_sess_id = res1["active_session_id"]
        assert initial_sess_id is not None

        # 5 consecutive polls while remaining plugged in
        for i in range(5):
            mock_batt.return_value["battery_percent"] = 50.0 + (i + 1) * 2.0
            res = collector.poll_once(db=test_db)
            assert res["success"] is True
            assert res["active_session_id"] == initial_sess_id
            assert res["transition_event"] is None

        # Assert exactly ONE session exists in DB
        total_sessions = test_db.query(ChargingSession).filter(ChargingSession.user_id == 1).count()
        assert total_sessions == 1


# =====================================================================
# 4. Restart Recovery Test
# =====================================================================
def test_restart_recovery_reconnects_open_session(test_db):
    """Simulates collector restarting while a session was already active in DB."""
    start_dt = datetime.now(timezone.utc) - timedelta(minutes=20)
    existing_session = ChargingSession(
        user_id=1,
        start_time=start_dt,
        start_battery_percent=45.0,
        end_time=None,
        data_source="REAL_WINDOWS",
    )
    test_db.add(existing_session)
    test_db.commit()
    test_db.refresh(existing_session)

    # Initialize a BRAND NEW collector instance (simulating app restart)
    new_collector = WindowsTelemetryService(target_user_id=1, poll_interval_seconds=120)
    assert new_collector.active_session_id is None

    # First poll after restart while still plugged in
    with patch("app.services.device_battery_service.device_battery_service.get_battery_status") as mock_batt, \
         patch.object(new_collector, "get_system_idle_seconds", return_value=0.5):
        mock_batt.return_value = {
            "available": True,
            "battery_percent": 55.0,
            "is_plugged_in": True,
            "seconds_left": None,
            "source": "WINDOWS_SYSTEM",
        }
        res = new_collector.poll_once(db=test_db)

        # Reconnected to existing session
        assert new_collector.active_session_id == existing_session.id
        # No duplicate session created
        assert test_db.query(ChargingSession).filter(ChargingSession.user_id == 1).count() == 1


# =====================================================================
# 5. Real vs Synthetic Separation Test
# =====================================================================
def test_real_vs_synthetic_separation(test_db):
    """Verifies sessions are distinguished by data_source and queries isolate them."""
    now = datetime.now(timezone.utc)

    # Add 2 synthetic sessions and 2 real sessions
    s1 = ChargingSession(user_id=1, start_time=now - timedelta(days=2), start_battery_percent=30, end_time=now - timedelta(days=2, hours=-2), end_battery_percent=80, data_source="SYNTHETIC")
    s2 = ChargingSession(user_id=1, start_time=now - timedelta(days=1), start_battery_percent=40, end_time=now - timedelta(days=1, hours=-2), end_battery_percent=85, data_source="SYNTHETIC")
    r1 = ChargingSession(user_id=1, start_time=now - timedelta(hours=10), start_battery_percent=25, end_time=now - timedelta(hours=8), end_battery_percent=80, data_source="REAL_WINDOWS")
    r2 = ChargingSession(user_id=1, start_time=now - timedelta(hours=5), start_battery_percent=35, end_time=now - timedelta(hours=3), end_battery_percent=80, data_source="REAL_WINDOWS")

    test_db.add_all([s1, s2, r1, r2])
    test_db.commit()

    real_sessions = test_db.query(ChargingSession).filter(ChargingSession.data_source == "REAL_WINDOWS").all()
    synth_sessions = test_db.query(ChargingSession).filter(ChargingSession.data_source == "SYNTHETIC").all()

    assert len(real_sessions) == 2
    assert len(synth_sessions) == 2
    assert all(s.data_source == "REAL_WINDOWS" for s in real_sessions)
    assert all(s.data_source == "SYNTHETIC" for s in synth_sessions)


# =====================================================================
# 6. Historical Leakage Prevention Test
# =====================================================================
def test_historical_leakage_prevention():
    """Verifies future sessions or concurrent sessions relative to t_0 are excluded from history."""
    t_0 = datetime(2026, 9, 10, 14, 0, 0, tzinfo=timezone.utc)

    # Session 1: Valid past session
    s_past = ChargingSession(
        id=1,
        user_id=1,
        start_time=t_0 - timedelta(days=1),
        end_time=t_0 - timedelta(days=1) + timedelta(hours=2),
        start_battery_percent=30.0,
        end_battery_percent=80.0,
        charging_duration_minutes=120.0,
        data_source="REAL_WINDOWS",
    )
    # Session 2: Future session (starts after t_0)
    s_future = ChargingSession(
        id=2,
        user_id=1,
        start_time=t_0 + timedelta(hours=2),
        end_time=t_0 + timedelta(hours=4),
        start_battery_percent=40.0,
        end_battery_percent=90.0,
        charging_duration_minutes=120.0,
        data_source="REAL_WINDOWS",
    )
    # Session 3: Current in-progress session (starts before t_0, ends after t_0)
    s_overlap = ChargingSession(
        id=3,
        user_id=1,
        start_time=t_0 - timedelta(minutes=30),
        end_time=t_0 + timedelta(hours=1),
        start_battery_percent=50.0,
        end_battery_percent=80.0,
        charging_duration_minutes=90.0,
        data_source="REAL_WINDOWS",
    )

    feat_res = feature_service.extract_features(
        user_id=1,
        plug_time=t_0,
        start_battery_pct=50.0,
        history_sessions=[s_past, s_future, s_overlap],
    )

    # Strictly only 1 past session should be counted; future and overlapping must be excluded!
    assert feat_res.history_count == 1


# =====================================================================
# 7. Collector Failure Recovery Test
# =====================================================================
def test_collector_failure_recovery(test_db):
    """Verifies sensor exceptions or None readings are caught safely without crashing."""
    collector = WindowsTelemetryService(target_user_id=1, poll_interval_seconds=120)

    # Mock sensor throwing an OS / Hardware exception
    with patch("app.services.device_battery_service.device_battery_service.get_battery_status") as mock_batt:
        mock_batt.side_effect = PermissionError("Access to battery sensor denied")

        # Must not raise an uncaught exception
        res = collector.poll_once(db=test_db)
        assert res["success"] is False
        assert "Access to battery sensor denied" in res["error"]

    # In next cycle, sensor recovers:
    with patch("app.services.device_battery_service.device_battery_service.get_battery_status") as mock_batt, \
         patch.object(collector, "get_system_idle_seconds", return_value=0.0):
        mock_batt.return_value = {
            "available": True,
            "battery_percent": 60.0,
            "is_plugged_in": False,
            "seconds_left": 4000,
            "source": "WINDOWS_SYSTEM",
        }
        res_rec = collector.poll_once(db=test_db)
        assert res_rec["success"] is True
        assert res_rec["battery_percent"] == 60.0


# =====================================================================
# 8. Sleep / Wake Gap Detection Test
# =====================================================================
def test_sleep_wake_gap_detection(test_db):
    """Verifies long gaps between polls are detected as sleep/suspend events."""
    collector = WindowsTelemetryService(target_user_id=1, poll_interval_seconds=120)
    t_start = datetime.now(timezone.utc) - timedelta(minutes=45)

    collector.last_poll_time = t_start
    collector.last_plugged_state = False

    with patch("app.services.device_battery_service.device_battery_service.get_battery_status") as mock_batt, \
         patch.object(collector, "get_system_idle_seconds", return_value=0.0):
        mock_batt.return_value = {
            "available": True,
            "battery_percent": 50.0,
            "is_plugged_in": False,
            "seconds_left": 4000,
            "source": "WINDOWS_SYSTEM",
        }
        res = collector.poll_once(db=test_db)
        assert res["success"] is True
        # Gap of ~45 minutes with a 120s poll interval -> sleep gap detected!
        assert res["sleep_gap_seconds"] > 2400.0
        assert collector.sleep_events_count == 1


# =====================================================================
# 9. Active vs Idle Measurement Test
# =====================================================================
def test_active_vs_idle_measurement(test_db):
    """Verifies that active and idle durations accumulate according to idle threshold."""
    collector = WindowsTelemetryService(target_user_id=1, poll_interval_seconds=120, idle_threshold_seconds=60.0)
    t_prev = datetime.now(timezone.utc) - timedelta(seconds=120)
    collector.last_poll_time = t_prev
    collector.last_plugged_state = False

    with patch("app.services.device_battery_service.device_battery_service.get_battery_status") as mock_batt:
        mock_batt.return_value = {
            "available": True,
            "battery_percent": 50.0,
            "is_plugged_in": False,
            "seconds_left": 4000,
            "source": "WINDOWS_SYSTEM",
        }

        # Scenario 1: User active (idle = 5s < 60s threshold)
        with patch.object(collector, "get_system_idle_seconds", return_value=5.0):
            res_act = collector.poll_once(db=test_db)
            assert res_act["is_user_active"] is True
            assert collector.today_active_seconds >= 115.0

        # Scenario 2: User idle (idle = 300s > 60s threshold)
        collector.last_poll_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        with patch.object(collector, "get_system_idle_seconds", return_value=300.0):
            res_idle = collector.poll_once(db=test_db)
            assert res_idle["is_user_active"] is False
            assert collector.today_idle_seconds >= 115.0


# =====================================================================
# 10. REST API Endpoints Integration Test
# =====================================================================
def test_telemetry_rest_api_endpoints(client, test_db):
    """Verifies the REST API routes for status, poll-now, sessions, and samples."""
    # 1. GET /api/telemetry/status
    res_status = client.get("/api/telemetry/status?user_id=1")
    assert res_status.status_code == 200
    st_json = res_status.json()
    assert "personalization_stage" in st_json
    assert "real_sessions_count" in st_json
    assert "privacy_notice" in st_json

    # 2. POST /api/telemetry/poll-now
    res_poll = client.post("/api/telemetry/poll-now?user_id=1")
    assert res_poll.status_code == 200
    assert res_poll.json()["success"] is True

    # 3. GET /api/telemetry/samples
    res_samples = client.get("/api/telemetry/samples?user_id=1")
    assert res_samples.status_code == 200
    assert isinstance(res_samples.json(), list)

    # 4. GET /api/telemetry/sessions
    res_sessions = client.get("/api/telemetry/sessions?user_id=1")
    assert res_sessions.status_code == 200
    assert isinstance(res_sessions.json(), list)
