"""
Integration tests for ML Service + Recommendation Engine + FastAPI REST backend.
Validates the complete production workflow:
1. Model service loading & schema verification
2. Cold-start, blended, and personalized prediction tiers
3. Smart recommendation generation with schedule solving
4. Database persistence and retrieval via GET endpoints
5. Midnight crossing and edge case validations
6. Missing-model graceful fallback
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.models.user import User
from app.models.charging_session import ChargingSession
from app.models.prediction import Prediction
from app.models.recommendation import Recommendation
from app.services.ml_service import ml_service
from app.services.feature_service import feature_service, ALL_PERSONALIZED_FEATURE_COLUMNS


@pytest.fixture
def client(db_session):
    """Provides a TestClient using the isolated in-memory test database."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user(db_session):
    """Creates and returns a test user."""
    user = User(name="Integration User", email="integration@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def seed_charging_sessions(db_session, user_id: int, count: int):
    """Helper to populate N realistic completed historical sessions."""
    base_time = datetime(2026, 8, 1, 22, 0, 0, tzinfo=timezone.utc)
    for i in range(count):
        start = base_time + timedelta(days=i)
        # Typically unplugs around 07:00 next day (9 hours = 540 min)
        duration = 540.0 + (i % 5) * 10.0
        end = start + timedelta(minutes=duration)
        session = ChargingSession(
            user_id=user_id,
            start_time=start,
            end_time=end,
            start_battery_percent=25.0 + (i % 3) * 5.0,
            end_battery_percent=100.0,
            charging_duration_minutes=duration,
            charger_type="standard",
            screen_usage_minutes=320.0,
            day_of_week=start.weekday(),
        )
        db_session.add(session)
    db_session.commit()


# ==============================================================================
# 1. Model Service Loading & Metadata Consistency
# ==============================================================================

def test_model_service_loading():
    """Verifies that MLService successfully caches both global and personalized models."""
    ml_service.load_models()
    assert ml_service.global_loaded is True
    assert ml_service.personalized_loaded is True
    health = ml_service.get_health_status()
    assert health["global_model"] == "loaded"
    assert health["personalized_model"] == "loaded"


def test_preprocessing_feature_consistency():
    """Verifies feature names and ordering strictly match personalized model metadata."""
    ml_service.load_models()
    if ml_service.pers_metadata and "features" in ml_service.pers_metadata:
        expected_features = ml_service.pers_metadata["features"]
        assert ALL_PERSONALIZED_FEATURE_COLUMNS == expected_features

    # Verify extracted DataFrame matches columns
    plug_time = datetime(2026, 9, 10, 22, 30, 0, tzinfo=timezone.utc)
    res = feature_service.extract_features(user_id=1, plug_time=plug_time, start_battery_pct=40.0)
    assert list(res.personalized_features.columns) == ALL_PERSONALIZED_FEATURE_COLUMNS


# ==============================================================================
# 2. Cold-Start Prediction (0 Sessions -> GLOBAL_BASELINE)
# ==============================================================================

def test_cold_start_prediction(client, sample_user):
    """New user with 0 completed sessions must receive GLOBAL_BASELINE prediction."""
    res = client.post(f"/api/predict/{sample_user.id}")
    assert res.status_code == 201
    data = res.json()

    assert data["user_id"] == sample_user.id
    assert data["prediction_source"] == "GLOBAL_BASELINE"
    assert data["history_count"] == 0
    assert 0.0 <= data["predicted_unplug_hour"] < 24.0
    assert ":" in data["predicted_unplug_time"]
    assert data["confidence_score"] > 0.0
    assert "prediction_id" in data


# ==============================================================================
# 3. Blended Prediction Tier (3-6 Sessions -> BLENDED)
# ==============================================================================

def test_blended_prediction(client, sample_user, db_session):
    """User with 4 sessions engages circular BLENDED strategy."""
    seed_charging_sessions(db_session, sample_user.id, count=4)

    res = client.post(f"/api/predict/{sample_user.id}")
    assert res.status_code == 201
    data = res.json()

    assert data["prediction_source"] == "BLENDED"
    assert data["history_count"] == 4
    assert 0.0 <= data["predicted_unplug_hour"] < 24.0


# ==============================================================================
# 4. Personalized Prediction Tier (7+ Sessions -> PERSONALIZED)
# ==============================================================================

def test_personalized_prediction(client, sample_user, db_session):
    """User with 10 sessions engages PERSONALIZED strategy."""
    seed_charging_sessions(db_session, sample_user.id, count=10)

    res = client.post(f"/api/predict/{sample_user.id}")
    assert res.status_code == 201
    data = res.json()

    assert data["prediction_source"] == "PERSONALIZED"
    assert data["history_count"] == 10
    assert 0.0 <= data["predicted_unplug_hour"] < 24.0


# ==============================================================================
# 5. Smart Recommendation Generation API
# ==============================================================================

def test_smart_recommendation_api(client, sample_user, db_session):
    """
    POST /api/recommendations/{user_id}/generate
    Executes prediction + recommendation, persisting both records.
    """
    seed_charging_sessions(db_session, sample_user.id, count=8)

    payload = {
        "current_battery_percent": 34.0,
        "charger_type": "fast",
        "current_temperature": 31.5,
        "preferred_target_soc": 80.0,
        "wants_full_charge": False,
        "minimum_required_soc": 70.0,
        "allow_delayed_charging": True,
        "plug_time": datetime(2026, 9, 10, 22, 0, 0, tzinfo=timezone.utc).isoformat(),
    }

    res = client.post(f"/api/recommendations/{sample_user.id}/generate", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert data["user_id"] == sample_user.id

    # Validate prediction block
    pred = data["prediction"]
    assert pred["prediction_source"] == "PERSONALIZED"
    assert pred["history_count"] == 8
    assert ":" in pred["predicted_unplug_time"]

    # Validate recommendation block
    rec = data["recommendation"]
    assert rec["mode"] in ["DELAYED_CHARGE", "CONSERVATIVE_CHARGE"]
    assert rec["current_soc"] == 34.0
    assert rec["target_soc"] == 80.0
    assert ":" in rec["recommended_start_time"]
    assert ":" in rec["estimated_finish_time"]
    assert rec["estimated_charging_minutes"] > 0.0
    assert len(rec["message"]) > 0

    # Validate persistence in database
    pred_db = db_session.query(Prediction).filter(Prediction.id == data["prediction_id"]).first()
    rec_db = db_session.query(Recommendation).filter(Recommendation.id == data["recommendation_id"]).first()
    assert pred_db is not None
    assert rec_db is not None
    assert rec_db.target_soc == 80.0


# ==============================================================================
# 6. End-to-End Workflow & Read Endpoints Consistency
# ==============================================================================

def test_end_to_end_workflow(client, db_session):
    """
    Complete end-to-end integration flow:
    1. Create user
    2. Seed completed history
    3. Generate prediction
    4. Generate smart recommendation
    5. Retrieve latest records via GET and verify consistency
    """
    # 1. Create user
    user_res = client.post("/api/users", json={"name": "End2End User", "email": "e2e@example.com"})
    assert user_res.status_code == 201
    user_id = user_res.json()["id"]

    # 2. Seed history
    seed_charging_sessions(db_session, user_id, count=12)

    # 3. Generate prediction
    pred_res = client.post(f"/api/predict/{user_id}")
    assert pred_res.status_code == 201
    pred_data = pred_res.json()

    # 4. Generate recommendation
    rec_res = client.post(f"/api/recommendations/{user_id}/generate", json={
        "current_battery_percent": 25.0,
        "preferred_target_soc": 85.0,
        "plug_time": datetime(2026, 9, 10, 22, 15, 0, tzinfo=timezone.utc).isoformat(),
    })
    assert rec_res.status_code == 201
    rec_data = rec_res.json()

    # 5. Retrieve latest prediction via GET /api/predictions/{user_id}/latest
    get_pred = client.get(f"/api/predictions/{user_id}/latest")
    assert get_pred.status_code == 200
    latest_pred = get_pred.json()
    assert latest_pred["user_id"] == user_id
    assert latest_pred["id"] == rec_data["prediction_id"]

    # 6. Retrieve latest recommendation via GET /api/recommendations/{user_id}/latest
    get_rec = client.get(f"/api/recommendations/{user_id}/latest")
    assert get_rec.status_code == 200
    latest_rec = get_rec.json()
    assert latest_rec["user_id"] == user_id
    assert latest_rec["id"] == rec_data["recommendation_id"]
    assert latest_rec["target_soc"] == 85.0


# ==============================================================================
# 7. Midnight Crossing Behavior
# ==============================================================================

def test_midnight_crossing_schedule(client, sample_user):
    """
    Plug-in late evening (23:30), unplug morning next day (07:30).
    Ensures start and finish times cross into next calendar day without negative duration.
    """
    plug_time = datetime(2026, 9, 10, 23, 30, 0, tzinfo=timezone.utc)
    res = client.post(f"/api/recommendations/{sample_user.id}/generate", json={
        "current_battery_percent": 30.0,
        "preferred_target_soc": 80.0,
        "plug_time": plug_time.isoformat(),
    })
    assert res.status_code == 201
    data = res.json()

    rec = data["recommendation"]
    start_dt = datetime.fromisoformat(rec["recommended_start_datetime"])
    finish_dt = datetime.fromisoformat(rec["estimated_finish_datetime"])

    assert finish_dt > start_dt
    assert finish_dt.date() == datetime(2026, 9, 11).date()
    assert rec["estimated_charging_minutes"] > 0.0


# ==============================================================================
# 8. User Preference Disallowing Delayed Charging
# ==============================================================================

def test_allow_delayed_charging_disabled(client, sample_user):
    """
    When allow_delayed_charging is False, engine must force immediate CHARGE_NOW.
    """
    plug_time = datetime(2026, 9, 10, 22, 0, 0, tzinfo=timezone.utc)
    res = client.post(f"/api/recommendations/{sample_user.id}/generate", json={
        "current_battery_percent": 40.0,
        "preferred_target_soc": 80.0,
        "allow_delayed_charging": False,
        "plug_time": plug_time.isoformat(),
    })
    assert res.status_code == 201
    data = res.json()

    rec = data["recommendation"]
    assert rec["mode"] == "CHARGE_NOW"
    assert rec["recommended_start_time"] == plug_time.strftime("%H:%M")


# ==============================================================================
# 9. Invalid Request & Error Handling
# ==============================================================================

def test_error_handling_invalid_requests(client, sample_user):
    """Verifies that invalid parameters return clean HTTP error codes without stack traces."""
    # Nonexistent user
    res = client.post("/api/predict/999999")
    assert res.status_code == 404

    # Invalid battery percent (> 100)
    res = client.post(f"/api/predict/{sample_user.id}", json={"current_battery_percent": 150.0})
    assert res.status_code in [400, 422]

    # Target SOC < minimum required SOC
    res = client.post(f"/api/recommendations/{sample_user.id}/generate", json={
        "current_battery_percent": 50.0,
        "preferred_target_soc": 60.0,
        "minimum_required_soc": 75.0,
    })
    assert res.status_code == 400
    assert "preferred_target_soc" in res.json()["detail"]


# ==============================================================================
# 10. Health Endpoint Status
# ==============================================================================

def test_extended_health_endpoint(client):
    """GET /health reports connectivity and loaded models."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["global_model"] == "loaded"
    assert data["personalized_model"] == "loaded"


# ==============================================================================
# 11. Missing Personalized Model Graceful Fallback
# ==============================================================================

def test_missing_personalized_model_fallback(client, sample_user, db_session):
    """
    When personalized model is missing or unavailable, the system safely falls back
    to GLOBAL_BASELINE without failing or raising 500.
    """
    seed_charging_sessions(db_session, sample_user.id, count=10)

    # Temporarily simulate missing personalized model
    saved_sin = ml_service.pers_sin_model
    saved_cos = ml_service.pers_cos_model
    try:
        ml_service.pers_sin_model = None
        ml_service.pers_cos_model = None

        res = client.post(f"/api/predict/{sample_user.id}")
        assert res.status_code == 201
        data = res.json()

        # Should safely fall back to GLOBAL_BASELINE
        assert data["prediction_source"] == "GLOBAL_BASELINE"
        assert 0.0 <= data["predicted_unplug_hour"] < 24.0
    finally:
        ml_service.pers_sin_model = saved_sin
        ml_service.pers_cos_model = saved_cos

