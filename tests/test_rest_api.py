from datetime import datetime, timedelta, timezone
from app.models.user import User
from app.models.prediction import Prediction
from app.models.recommendation import Recommendation


# -----------------------------------------------------------------------------
# 1. Health endpoint
# -----------------------------------------------------------------------------
def test_1_health_endpoints(client):
    """Test both /health and /api/health return 200 with database status."""
    res1 = client.get("/health")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "healthy"
    assert data1["database"] == "connected"

    res2 = client.get("/api/health")
    assert res2.status_code == 200
    assert res2.json()["status"] == "healthy"


# -----------------------------------------------------------------------------
# 2. Create user
# -----------------------------------------------------------------------------
def test_2_create_user(client):
    """Test POST /api/users creates a user and returns 201 Created."""
    payload = {
        "name": "Demo User",
        "email": "demo@example.com"
    }
    response = client.post("/api/users", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["name"] == "Demo User"
    assert data["email"] == "demo@example.com"
    assert "created_at" in data


# -----------------------------------------------------------------------------
# 3. Duplicate email handling
# -----------------------------------------------------------------------------
def test_3_duplicate_email_handling(client):
    """Test POST /api/users rejects duplicate emails with 400 Bad Request."""
    payload = {
        "name": "First Registration",
        "email": "unique@example.com"
    }
    res1 = client.post("/api/users", json=payload)
    assert res1.status_code == 201

    # Duplicate attempt
    res2 = client.post("/api/users", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"].lower()


# -----------------------------------------------------------------------------
# 4. Get user
# -----------------------------------------------------------------------------
def test_4_get_user(client):
    """Test GET /api/users/{user_id} returns user data."""
    user_res = client.post("/api/users", json={"name": "Alice Green", "email": "alice@battery.ai"})
    user_id = user_res.json()["id"]

    response = client.get(f"/api/users/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["name"] == "Alice Green"
    assert data["email"] == "alice@battery.ai"


# -----------------------------------------------------------------------------
# 5. Invalid user
# -----------------------------------------------------------------------------
def test_5_invalid_user(client):
    """Test GET /api/users for nonexistent ID (404) and invalid ID format (400)."""
    # Nonexistent user
    res_not_found = client.get("/api/users/999999")
    assert res_not_found.status_code == 404
    assert "not found" in res_not_found.json()["detail"].lower()

    # Invalid user ID (e.g. 0 or negative)
    res_bad_id = client.get("/api/users/-5")
    assert res_bad_id.status_code == 400
    assert "positive integer" in res_bad_id.json()["detail"].lower()


# -----------------------------------------------------------------------------
# 6. Create charging session
# -----------------------------------------------------------------------------
def test_6_create_charging_session(client):
    """Test POST /api/charging-sessions records a new session."""
    user = client.post("/api/users", json={"name": "Bob Charger", "email": "bob@battery.ai"}).json()
    user_id = user["id"]

    now = datetime.now(timezone.utc)
    session_payload = {
        "user_id": user_id,
        "start_time": now.isoformat(),
        "start_battery_percent": 24.5,
        "charger_type": "fast_dc",
        "screen_usage_minutes": 10.0,
        "average_temperature": 32.1,
        "day_of_week": now.weekday(),
    }
    response = client.post("/api/charging-sessions", json=session_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["user_id"] == user_id
    assert data["start_battery_percent"] == 24.5
    assert data["charger_type"] == "fast_dc"
    assert data["screen_usage_minutes"] == 10.0
    assert data["average_temperature"] == 32.1


# -----------------------------------------------------------------------------
# 7. List user charging sessions
# -----------------------------------------------------------------------------
def test_7_list_user_charging_sessions(client):
    """Test GET /api/charging-sessions/{user_id} lists all user sessions."""
    user = client.post("/api/users", json={"name": "Charlie", "email": "charlie@battery.ai"}).json()
    user_id = user["id"]

    # Initially empty list
    empty_res = client.get(f"/api/charging-sessions/{user_id}")
    assert empty_res.status_code == 200
    assert empty_res.json() == []

    # Add two sessions
    now = datetime.now(timezone.utc)
    client.post("/api/charging-sessions", json={
        "user_id": user_id,
        "start_time": (now - timedelta(hours=24)).isoformat(),
        "start_battery_percent": 30.0,
    })
    client.post("/api/charging-sessions", json={
        "user_id": user_id,
        "start_time": now.isoformat(),
        "start_battery_percent": 45.0,
    })

    res = client.get(f"/api/charging-sessions/{user_id}")
    assert res.status_code == 200
    sessions = res.json()
    assert len(sessions) == 2
    # Ordered by start_time descending
    assert sessions[0]["start_battery_percent"] == 45.0
    assert sessions[1]["start_battery_percent"] == 30.0


# -----------------------------------------------------------------------------
# 8. Latest charging session
# -----------------------------------------------------------------------------
def test_8_latest_charging_session(client):
    """Test GET /api/charging-sessions/{user_id}/latest returns latest or 404."""
    user = client.post("/api/users", json={"name": "Dana", "email": "dana@battery.ai"}).json()
    user_id = user["id"]

    # 404 when no session exists
    empty_latest = client.get(f"/api/charging-sessions/{user_id}/latest")
    assert empty_latest.status_code == 404

    # Add a session
    client.post("/api/charging-sessions", json={
        "user_id": user_id,
        "start_battery_percent": 55.0,
    })

    res = client.get(f"/api/charging-sessions/{user_id}/latest")
    assert res.status_code == 200
    assert res.json()["start_battery_percent"] == 55.0


# -----------------------------------------------------------------------------
# 9. Add battery reading
# -----------------------------------------------------------------------------
def test_9_add_battery_reading(client):
    """Test POST /api/battery-readings records telemetry reading."""
    user = client.post("/api/users", json={"name": "Eve Sensor", "email": "eve@battery.ai"}).json()
    user_id = user["id"]

    now = datetime.now(timezone.utc)
    reading_payload = {
        "user_id": user_id,
        "timestamp": now.isoformat(),
        "voltage": 4.05,
        "current": 1.45,
        "temperature": 29.8,
        "battery_percent": 68.0,
    }
    response = client.post("/api/battery-readings", json=reading_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["user_id"] == user_id
    assert data["voltage"] == 4.05
    assert data["current"] == 1.45
    assert data["temperature"] == 29.8
    assert data["battery_percent"] == 68.0


# -----------------------------------------------------------------------------
# 10. List battery readings
# -----------------------------------------------------------------------------
def test_10_list_battery_readings(client):
    """Test GET /api/battery-readings/{user_id} returns readings ordered by timestamp."""
    user = client.post("/api/users", json={"name": "Frank", "email": "frank@battery.ai"}).json()
    user_id = user["id"]

    now = datetime.now(timezone.utc)
    client.post("/api/battery-readings", json={
        "user_id": user_id,
        "timestamp": (now - timedelta(minutes=10)).isoformat(),
        "voltage": 3.8,
        "current": 1.0,
        "temperature": 25.0,
        "battery_percent": 50.0,
    })
    client.post("/api/battery-readings", json={
        "user_id": user_id,
        "timestamp": now.isoformat(),
        "voltage": 3.9,
        "current": 1.2,
        "temperature": 26.5,
        "battery_percent": 55.0,
    })

    res = client.get(f"/api/battery-readings/{user_id}?order=desc")
    assert res.status_code == 200
    readings = res.json()
    assert len(readings) == 2
    assert readings[0]["battery_percent"] == 55.0
    assert readings[1]["battery_percent"] == 50.0


# -----------------------------------------------------------------------------
# 11. Latest battery reading
# -----------------------------------------------------------------------------
def test_11_latest_battery_reading(client):
    """Test GET /api/battery-readings/{user_id}/latest returns newest reading or 404."""
    user = client.post("/api/users", json={"name": "Grace", "email": "grace@battery.ai"}).json()
    user_id = user["id"]

    # 404 when no reading
    assert client.get(f"/api/battery-readings/{user_id}/latest").status_code == 404

    # Ingest reading
    client.post("/api/battery-readings", json={
        "user_id": user_id,
        "voltage": 4.1,
        "current": 1.5,
        "temperature": 30.0,
        "battery_percent": 82.0,
    })

    res = client.get(f"/api/battery-readings/{user_id}/latest")
    assert res.status_code == 200
    assert res.json()["battery_percent"] == 82.0


# -----------------------------------------------------------------------------
# 12. Predictions API
# -----------------------------------------------------------------------------
def test_12_predictions_api(client, db_session):
    """Test GET /api/predictions/{user_id} returns previous ML predictions without fabrication."""
    user = client.post("/api/users", json={"name": "Hank", "email": "hank@battery.ai"}).json()
    user_id = user["id"]

    # Empty list when no predictions exist
    res_empty = client.get(f"/api/predictions/{user_id}")
    assert res_empty.status_code == 200
    assert res_empty.json() == []

    # 404 on latest when no predictions exist
    assert client.get(f"/api/predictions/{user_id}/latest").status_code == 404

    # Seed an ML prediction in DB
    now = datetime.now(timezone.utc)
    pred = Prediction(
        user_id=user_id,
        predicted_unplug_time=now + timedelta(hours=7),
        confidence_score=0.88,
        model_version="1.2.0",
    )
    db_session.add(pred)
    db_session.commit()

    # Query predictions
    res = client.get(f"/api/predictions/{user_id}")
    assert res.status_code == 200
    preds = res.json()
    assert len(preds) == 1
    assert preds[0]["confidence_score"] == 0.88
    assert preds[0]["model_version"] == "1.2.0"

    # Query latest prediction
    latest_res = client.get(f"/api/predictions/{user_id}/latest")
    assert latest_res.status_code == 200
    assert latest_res.json()["confidence_score"] == 0.88


# -----------------------------------------------------------------------------
# 13. Recommendations API
# -----------------------------------------------------------------------------
def test_13_recommendations_api(client, db_session):
    """Test GET /api/recommendations/{user_id} returns previous recommendations."""
    user = client.post("/api/users", json={"name": "Iris", "email": "iris@battery.ai"}).json()
    user_id = user["id"]

    # Empty list when none exist
    empty_res = client.get(f"/api/recommendations/{user_id}")
    assert empty_res.status_code == 200
    assert empty_res.json() == []

    # Create a recommendation via charging session initiation
    session_res = client.post("/api/charging-sessions", json={
        "user_id": user_id,
        "start_battery_percent": 15.0,
    })
    assert session_res.status_code == 201

    # Recommendations should now contain the generated recommendation
    res = client.get(f"/api/recommendations/{user_id}")
    assert res.status_code == 200
    recs = res.json()
    assert len(recs) >= 1
    assert recs[0]["target_soc"] == 80.0
    assert recs[0]["recommendation_message"] is not None

    # Latest recommendation
    latest_res = client.get(f"/api/recommendations/{user_id}/latest")
    assert latest_res.status_code == 200
    assert latest_res.json()["target_soc"] == 80.0


# -----------------------------------------------------------------------------
# 14. Validation errors
# -----------------------------------------------------------------------------
def test_14_validation_errors(client):
    """Test input validations for battery %, email format, duration, and IDs."""
    user = client.post("/api/users", json={"name": "Jack", "email": "jack@battery.ai"}).json()
    user_id = user["id"]

    # 1. Invalid email format
    invalid_email_res = client.post("/api/users", json={"name": "Invalid", "email": "not-an-email"})
    assert invalid_email_res.status_code == 422

    # 2. Battery percentage > 100 on charging session
    over_100_session = client.post("/api/charging-sessions", json={
        "user_id": user_id,
        "start_battery_percent": 120.0,
    })
    assert over_100_session.status_code == 422

    # 3. Battery percentage < 0 on charging session
    under_0_session = client.post("/api/charging-sessions", json={
        "user_id": user_id,
        "start_battery_percent": -5.0,
    })
    assert under_0_session.status_code == 422

    # 4. Battery reading percent > 100
    over_reading = client.post("/api/battery-readings", json={
        "user_id": user_id,
        "voltage": 4.0,
        "current": 1.0,
        "temperature": 25.0,
        "battery_percent": 105.0,
    })
    assert over_reading.status_code == 422

    # 5. Negative charging duration
    negative_duration = client.post("/api/charging-sessions", json={
        "user_id": user_id,
        "start_battery_percent": 50.0,
        "charging_duration_minutes": -10.0,
    })
    assert negative_duration.status_code == 422

    # 6. Missing required fields in battery reading (missing voltage)
    missing_fields = client.post("/api/battery-readings", json={
        "user_id": user_id,
        "battery_percent": 50.0,
    })
    assert missing_fields.status_code == 422


# -----------------------------------------------------------------------------
# 15. Foreign-key relationships
# -----------------------------------------------------------------------------
def test_15_foreign_key_relationships(client):
    """Test that all entity endpoints reject operations on non-existent users with 404."""
    fake_user_id = 888888

    # Session create with non-existent user
    res_session = client.post("/api/charging-sessions", json={
        "user_id": fake_user_id,
        "start_battery_percent": 40.0,
    })
    assert res_session.status_code == 404
    assert "not found" in res_session.json()["detail"].lower()

    # Reading create with non-existent user
    res_reading = client.post("/api/battery-readings", json={
        "user_id": fake_user_id,
        "voltage": 4.0,
        "current": 1.0,
        "temperature": 25.0,
        "battery_percent": 50.0,
    })
    assert res_reading.status_code == 404

    # Predictions query with non-existent user
    res_pred = client.get(f"/api/predictions/{fake_user_id}")
    assert res_pred.status_code == 404

    # Recommendations query with non-existent user
    res_rec = client.get(f"/api/recommendations/{fake_user_id}")
    assert res_rec.status_code == 404

    # Charging sessions query with non-existent user
    res_sess_list = client.get(f"/api/charging-sessions/{fake_user_id}")
    assert res_sess_list.status_code == 404
