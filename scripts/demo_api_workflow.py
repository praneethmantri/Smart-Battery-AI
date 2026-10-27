"""
Manual Demonstration Script - Smart Battery AI Production Workflow
===================================================================
Executes the live end-to-end API pipeline:
1. POST /api/users (Create test demo user)
2. POST /api/charging-sessions (Seed completed history)
3. POST /api/predict/{user_id} (Generate ML prediction)
4. POST /api/recommendations/{user_id}/generate (Generate smart recommendation)
5. GET /api/predictions/{user_id}/latest (Retrieve persisted prediction)
6. GET /api/recommendations/{user_id}/latest (Retrieve persisted recommendation)

Prints actual runtime JSON payloads for documentation.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

# Ensure project root and backend are on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient
from app.main import app


def run_demo():
    client = TestClient(app)

    print("=" * 80)
    print("SMART BATTERY AI - LIVE PRODUCTION API WORKFLOW DEMONSTRATION")
    print("=" * 80)

    # 1. POST /api/users
    print("\n--- 1. POST /api/users (Provision User) ---")
    user_payload = {
        "name": "Sarah Demo",
        "email": f"sarah_demo_{int(datetime.now().timestamp())}@example.com"
    }
    r1 = client.post("/api/users", json=user_payload)
    print(f"Status: {r1.status_code}")
    print(json.dumps(r1.json(), indent=2))
    user_id = r1.json()["id"]

    # 2. Seed completed charging history
    print(f"\n--- 2. POST /api/charging-sessions (Seeding History for User {user_id}) ---")
    base_time = datetime(2026, 8, 15, 22, 30, 0, tzinfo=timezone.utc)
    for i in range(12):
        start = base_time + timedelta(days=i)
        duration = 510.0 + (i % 4) * 15.0  # ~8.5 hours overnight session
        end = start + timedelta(minutes=duration)
        sess_payload = {
            "user_id": user_id,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "start_battery_percent": 25.0 + (i % 3) * 5.0,
            "end_battery_percent": 100.0,
            "charging_duration_minutes": duration,
            "charger_type": "standard",
            "screen_usage_minutes": 310.0,
        }
        client.post("/api/charging-sessions", json=sess_payload)
    print(f"Seeded 12 completed historical charging sessions for user {user_id}.")

    # 3. POST /api/predict/{user_id}
    print(f"\n--- 3. POST /api/predict/{user_id} (Execute Unplug Prediction) ---")
    pred_req = {
        "plug_time": datetime(2026, 9, 10, 22, 0, 0, tzinfo=timezone.utc).isoformat(),
        "current_battery_percent": 32.0,
        "charger_type": "fast",
    }
    r3 = client.post(f"/api/predict/{user_id}", json=pred_req)
    print(f"Status: {r3.status_code}")
    print(json.dumps(r3.json(), indent=2))

    # 4. POST /api/recommendations/{user_id}/generate
    print(f"\n--- 4. POST /api/recommendations/{user_id}/generate (Generate Smart Recommendation) ---")
    rec_req = {
        "current_battery_percent": 34.0,
        "charger_type": "fast",
        "current_temperature": 31.5,
        "estimated_charging_rate_percent_per_hour": 30.0,
        "preferred_target_soc": 80.0,
        "wants_full_charge": False,
        "minimum_required_soc": 70.0,
        "allow_delayed_charging": True,
        "plug_time": datetime(2026, 9, 10, 22, 15, 0, tzinfo=timezone.utc).isoformat(),
    }
    r4 = client.post(f"/api/recommendations/{user_id}/generate", json=rec_req)
    print(f"Status: {r4.status_code}")
    print(json.dumps(r4.json(), indent=2))

    # 5. GET /api/predictions/{user_id}/latest
    print(f"\n--- 5. GET /api/predictions/{user_id}/latest (Retrieve Stored Prediction) ---")
    r5 = client.get(f"/api/predictions/{user_id}/latest")
    print(f"Status: {r5.status_code}")
    print(json.dumps(r5.json(), indent=2))

    # 6. GET /api/recommendations/{user_id}/latest
    print(f"\n--- 6. GET /api/recommendations/{user_id}/latest (Retrieve Stored Recommendation) ---")
    r6 = client.get(f"/api/recommendations/{user_id}/latest")
    print(f"Status: {r6.status_code}")
    print(json.dumps(r6.json(), indent=2))

    print("\n" + "=" * 80)
    print("LIVE DEMONSTRATION EXECUTED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()
