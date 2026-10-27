"""
End-to-End Quality Assurance and Release Readiness Verification Script.
Executes complete live flow with FastAPI, real database, ML models, and host battery telemetry.
"""

import os
import sys
from datetime import datetime, timezone
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.charging_session import ChargingSession
from app.models.prediction import Prediction
from app.models.recommendation import Recommendation
from app.services.device_battery_service import device_battery_service

def run_qa_verification():
    print("=" * 70)
    print("SMART BATTERY AI - END-TO-END QUALITY ASSURANCE & RELEASE CHECK")
    print("=" * 70)

    client = TestClient(app)

    # 1. System Health Check
    print("\n[Step 1] Verifying System Health...")
    health_resp = client.get("/health")
    assert health_resp.status_code == 200, f"Health check failed: {health_resp.text}"
    health = health_resp.json()
    print(f" -> Status: {health['status']}")
    print(f" -> Database: {health['database']}")
    print(f" -> Global Model: {health['global_model']}")
    print(f" -> Personalized Model: {health['personalized_model']}")
    assert health["status"] == "healthy"
    assert health["database"] == "connected"
    assert health["global_model"] == "loaded"
    assert health["personalized_model"] == "loaded"

    # 2. Live Windows Device Battery Check
    print("\n[Step 2] Testing Live Windows Device Battery via psutil...")
    batt_resp = client.get("/api/device-battery")
    assert batt_resp.status_code == 200, f"Device battery API failed: {batt_resp.text}"
    batt = batt_resp.json()
    print(f" -> Available: {batt['available']}")
    print(f" -> Battery Percent: {batt['battery_percent']}%")
    print(f" -> Power Plugged In: {batt['is_plugged_in']}")
    print(f" -> Seconds Left: {batt['seconds_left']}")
    print(f" -> Source: {batt['source']}")
    assert "available" in batt
    assert "source" in batt

    detected_soc = batt["battery_percent"] if batt["available"] else 50.0

    # 3. User Verification & Database State
    print("\n[Step 3] Verifying User Profiles in Database...")
    db = SessionLocal()
    user1 = db.query(User).filter(User.id == 1).first()
    if not user1:
        user1 = User(name="Sarah Demo", email="sarah.demo@campus.edu")
        db.add(user1)
        db.commit()
        db.refresh(user1)
        print(f" -> Created User 1: {user1.name}")
    else:
        print(f" -> Found User 1: {user1.name} (id={user1.id})")

    # Ensure User 2 exists for empty-history / cold-start verification
    user2 = db.query(User).filter(User.id == 2).first()
    if not user2:
        user2 = User(name="Alex Chen (New User)", email="alex.chen.new@campus.edu")
        db.add(user2)
        db.commit()
        db.refresh(user2)
        print(f" -> Created User 2 (Cold-Start): {user2.name} (id={user2.id})")
    else:
        print(f" -> Found User 2: {user2.name} (id={user2.id})")

    u1_sessions_count = db.query(ChargingSession).filter(ChargingSession.user_id == 1).count()
    u2_sessions_count = db.query(ChargingSession).filter(ChargingSession.user_id == 2).count()
    print(f" -> User 1 Historical Sessions in DB: {u1_sessions_count}")
    print(f" -> User 2 Historical Sessions in DB: {u2_sessions_count}")

    # 4. Multi-Tier Prediction Verification
    print("\n[Step 4] Testing ML Unplug Prediction for User 1 (Personalized)...")
    pred_payload = {
        "current_battery_percent": detected_soc,
        "plug_time": datetime.now(timezone.utc).isoformat(),
        "charger_type": "fast",
        "previous_day_usage_minutes": 520,
    }
    pred_resp1 = client.post("/api/predict/1", json=pred_payload)
    assert pred_resp1.status_code == 201, f"Prediction failed for user 1: {pred_resp1.text}"
    pred_data1 = pred_resp1.json()
    print(f" -> User 1 Predicted Unplug: {pred_data1['predicted_unplug_time']}")
    print(f" -> User 1 Prediction Source: {pred_data1['prediction_source']}")
    print(f" -> User 1 Confidence: {pred_data1['confidence_score']:.2f} ({pred_data1['confidence_level']})")
    print(f" -> User 1 History Count: {pred_data1['history_count']}")
    assert pred_data1["prediction_source"] == "PERSONALIZED"
    assert pred_data1["history_count"] >= 7

    print("\n[Step 4b] Testing Cold-Start ML Prediction for User 2 (0 Sessions)...")
    pred_resp2 = client.post("/api/predict/2", json=pred_payload)
    assert pred_resp2.status_code == 201, f"Prediction failed for user 2: {pred_resp2.text}"
    pred_data2 = pred_resp2.json()
    print(f" -> User 2 Predicted Unplug: {pred_data2['predicted_unplug_time']}")
    print(f" -> User 2 Prediction Source: {pred_data2['prediction_source']}")
    print(f" -> User 2 History Count: {pred_data2['history_count']}")
    assert pred_data2["prediction_source"] == "GLOBAL_BASELINE"
    assert pred_data2["history_count"] == 0

    # 5. Smart Recommendation Generation Using Live Detected Battery
    print(f"\n[Step 5] Generating Smart Recommendation using Live Detected SoC ({detected_soc}%)...")
    rec_payload = {
        "current_battery_percent": detected_soc,
        "preferred_target_soc": 80.0,
        "minimum_required_soc": 70.0,
        "wants_full_charge": False,
        "allow_delayed_charging": True,
        "charger_type": "fast",
        "current_temperature": 32.5,
        "estimated_charging_rate_percent_per_hour": 40.0,
    }
    rec_resp = client.post("/api/recommendations/1/generate", json=rec_payload)
    assert rec_resp.status_code == 201, f"Recommendation failed: {rec_resp.text}"
    rec_data = rec_resp.json()
    rec_detail = rec_data["recommendation"]
    pred_summary = rec_data["prediction"]

    print(f" -> Recommendation ID: {rec_data['recommendation_id']}")
    print(f" -> Mode: {rec_detail['mode']}")
    print(f" -> Current SoC used: {rec_detail['current_soc']}%")
    print(f" -> Target SoC: {rec_detail['target_soc']}%")
    print(f" -> Recommended Start: {rec_detail['recommended_start_time']}")
    print(f" -> Estimated Finish: {rec_detail['estimated_finish_time']}")
    print(f" -> Predicted Unplug: {pred_summary['predicted_unplug_time']}")
    print(f" -> Message: {rec_detail['message']}")
    print(f" -> Reason: {rec_detail['reason']}")

    assert rec_detail["current_soc"] == detected_soc, "Recommendation did not use the actual live device SoC!"
    assert rec_detail["mode"] in ["DELAYED_CHARGE", "CHARGE_NOW", "CONSERVATIVE_CHARGE", "HOLD_AT_THRESHOLD"]

    # 6. Database Persistence Verification
    print("\n[Step 6] Verifying Database Persistence...")
    persisted_rec = db.query(Recommendation).filter(Recommendation.id == rec_data["recommendation_id"]).first()
    assert persisted_rec is not None, "Recommendation was not persisted to database!"
    print(f" -> Verified Recommendation #{persisted_rec.id} in DB: user={persisted_rec.user_id}, mode={persisted_rec.mode}")

    persisted_pred = db.query(Prediction).filter(Prediction.id == rec_data["prediction_id"]).first()
    assert persisted_pred is not None, "Prediction was not persisted to database!"
    print(f" -> Verified Prediction #{persisted_pred.id} in DB: unplug={persisted_pred.predicted_unplug_time}")

    # 7. Validation of Edge & Error Cases
    print("\n[Step 7] Testing Input Validation & Error Handling (Controlled Messages, No Tracebacks)...")

    # Invalid SoC < 0 (Pydantic / FastAPI schema validation returns 422 or 400)
    bad_soc1 = client.post("/api/recommendations/1/generate", json={**rec_payload, "current_battery_percent": -10.0})
    assert bad_soc1.status_code in [400, 422], f"Expected 400/422 got {bad_soc1.status_code}"
    print(f" -> Negative SoC rejected: {bad_soc1.json()}")

    # Invalid SoC > 100
    bad_soc2 = client.post("/api/recommendations/1/generate", json={**rec_payload, "current_battery_percent": 150.0})
    assert bad_soc2.status_code in [400, 422], f"Expected 400/422 got {bad_soc2.status_code}"
    print(f" -> Overflow SoC rejected: {bad_soc2.json()}")

    # Invalid Target SOC < Min Required SOC
    bad_target = client.post("/api/recommendations/1/generate", json={**rec_payload, "preferred_target_soc": 60.0, "minimum_required_soc": 75.0})
    assert bad_target.status_code in [400, 422], f"Expected 400/422 got {bad_target.status_code}"
    print(f" -> Target < Min rejected: {bad_target.json()}")

    # Negative charging rate
    bad_rate = client.post("/api/recommendations/1/generate", json={**rec_payload, "estimated_charging_rate_percent_per_hour": -5.0})
    assert bad_rate.status_code in [400, 422], f"Expected 400/422 got {bad_rate.status_code}"
    print(f" -> Negative rate rejected: {bad_rate.json()}")

    # Non-existent user
    bad_user = client.post("/api/recommendations/99999/generate", json=rec_payload)
    assert bad_user.status_code == 404
    print(f" -> Unknown user rejected: {bad_user.json()['detail']}")

    # 8. User Switching & Charging History Retrieval
    print("\n[Step 8] Verifying User Switching & History Retrieval...")
    u1_hist = client.get("/api/charging-sessions/1?limit=10").json()
    u2_hist = client.get("/api/charging-sessions/2?limit=10").json()
    print(f" -> User 1 history records returned: {len(u1_hist)}")
    print(f" -> User 2 history records returned: {len(u2_hist)} (proper empty state)")
    assert len(u1_hist) > 0, "User 1 should have historical records"
    assert len(u2_hist) == 0, "User 2 should return empty array [] without mixing mock records"

    db.close()
    print("\n" + "=" * 70)
    print("ALL END-TO-END CHECKS AND VALIDATIONS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_qa_verification()
