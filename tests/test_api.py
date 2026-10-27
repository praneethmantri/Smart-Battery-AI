from datetime import datetime, timezone


def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_start_charging_session(client):
    payload = {
        "user_id": 42,
        "plug_time": datetime.now(timezone.utc).isoformat(),
        "start_battery_pct": 25.0,
        "target_battery_pct": 100.0,
        "charger_type": "standard_ac",
    }
    response = client.post("/api/v1/charging/sessions", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == 42
    assert "recommendation" in data
    assert data["recommendation"]["hold_at_pct"] == 80.0
    assert "predicted_unplug_time" in data


def test_end_charging_session(client):
    # 1. Start a session
    start_payload = {
        "user_id": 42,
        "plug_time": datetime.now(timezone.utc).isoformat(),
        "start_battery_pct": 20.0,
        "target_battery_pct": 100.0,
        "charger_type": "standard_ac",
    }
    create_res = client.post("/api/v1/charging/sessions", json=start_payload)
    session_id = create_res.json()["session_id"]

    # 2. End the session
    end_payload = {
        "unplug_time": datetime.now(timezone.utc).isoformat(),
        "end_battery_pct": 95.0,
    }
    end_res = client.post(f"/api/v1/charging/sessions/{session_id}/end", json=end_payload)
    assert end_res.status_code == 200
    data = end_res.json()
    assert data["id"] == session_id
    assert data["end_battery_percent"] == 95.0


def test_list_sessions(client):
    response = client.get("/api/v1/charging/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert isinstance(data["sessions"], list)
