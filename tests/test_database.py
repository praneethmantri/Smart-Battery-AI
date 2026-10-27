from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.exc import IntegrityError
from app.models.user import User
from app.models.charging_session import ChargingSession
from app.models.battery_reading import BatteryReading
from app.models.prediction import Prediction
from app.models.recommendation import Recommendation
from app.db.base import Base
from app.db.init_db import init_db


def test_init_db_creates_all_tables(db_session):
    """Verify that all five required tables are registered in the metadata and exist."""
    table_names = Base.metadata.tables.keys()
    assert "users" in table_names
    assert "charging_sessions" in table_names
    assert "battery_readings" in table_names
    assert "predictions" in table_names
    assert "charging_recommendations" in table_names


def test_create_user(db_session):
    """Test user creation and unique email constraint."""
    user = User(name="Alice Smith", email="alice@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.name == "Alice Smith"
    assert user.email == "alice@example.com"
    assert user.created_at is not None

    # Test duplicate email failure
    duplicate_user = User(name="Alice Clone", email="alice@example.com")
    db_session.add(duplicate_user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_create_charging_session_with_relationships(db_session):
    """Test ChargingSession with all required fields and user relationship."""
    user = User(name="Bob Johnson", email="bob@example.com")
    db_session.add(user)
    db_session.commit()

    now = datetime.now(timezone.utc)
    later = now + timedelta(hours=7, minutes=30)

    session = ChargingSession(
        user_id=user.id,
        start_time=now,
        end_time=later,
        start_battery_percent=22.5,
        end_battery_percent=100.0,
        average_temperature=31.2,
        charging_duration_minutes=450.0,
        charger_type="fast_dc",
        screen_usage_minutes=15.0,
        day_of_week=now.weekday(),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    assert session.id is not None
    assert session.user_id == user.id
    assert session.start_battery_percent == 22.5
    assert session.end_battery_percent == 100.0
    assert session.average_temperature == 31.2
    assert session.charging_duration_minutes == 450.0
    assert session.charger_type == "fast_dc"
    assert session.screen_usage_minutes == 15.0
    assert session.day_of_week == now.weekday()
    assert session.created_at is not None

    # Test bidirectional relationship
    assert session.user.name == "Bob Johnson"
    assert len(user.charging_sessions) == 1
    assert user.charging_sessions[0].id == session.id


def test_battery_reading_model(db_session):
    """Test BatteryReading model fields, constraints, and relationship."""
    user = User(name="Charlie", email="charlie@example.com")
    db_session.add(user)
    db_session.commit()

    now = datetime.now(timezone.utc)
    reading = BatteryReading(
        user_id=user.id,
        timestamp=now,
        voltage=4.15,
        current=1.85,
        temperature=28.4,
        battery_percent=78.0,
    )
    db_session.add(reading)
    db_session.commit()
    db_session.refresh(reading)

    assert reading.id is not None
    assert reading.voltage == 4.15
    assert reading.current == 1.85
    assert reading.temperature == 28.4
    assert reading.battery_percent == 78.0
    assert reading.user.id == user.id
    assert len(user.battery_readings) == 1


def test_prediction_model(db_session):
    """Test Prediction model fields and user relationship."""
    user = User(name="Dana", email="dana@example.com")
    db_session.add(user)
    db_session.commit()

    predicted_time = datetime.now(timezone.utc) + timedelta(hours=8)
    prediction = Prediction(
        user_id=user.id,
        predicted_unplug_time=predicted_time,
        confidence_score=0.91,
        model_version="2.1.0",
    )
    db_session.add(prediction)
    db_session.commit()
    db_session.refresh(prediction)

    assert prediction.id is not None
    assert prediction.user_id == user.id
    assert prediction.predicted_unplug_time.replace(tzinfo=timezone.utc) == predicted_time
    assert prediction.confidence_score == 0.91
    assert prediction.model_version == "2.1.0"
    assert prediction.created_at is not None
    assert len(user.predictions) == 1


def test_recommendation_model(db_session):
    """Test Recommendation model fields, session link, and user relationship."""
    user = User(name="Eve", email="eve@example.com")
    db_session.add(user)
    db_session.commit()

    session = ChargingSession(
        user_id=user.id,
        start_time=datetime.now(timezone.utc),
        start_battery_percent=15.0,
    )
    db_session.add(session)
    db_session.commit()

    unplug_time = datetime.now(timezone.utc) + timedelta(hours=8)
    start_time = datetime.now(timezone.utc) + timedelta(hours=6, minutes=30)

    rec = Recommendation(
        user_id=user.id,
        session_id=session.id,
        predicted_unplug_time=unplug_time,
        recommended_start_time=start_time,
        target_soc=80.0,
        recommendation_message="Hold at 80% SoC until morning top-off.",
    )
    db_session.add(rec)
    db_session.commit()
    db_session.refresh(rec)

    assert rec.id is not None
    assert rec.user_id == user.id
    assert rec.session_id == session.id
    assert rec.predicted_unplug_time.replace(tzinfo=timezone.utc) == unplug_time
    assert rec.recommended_start_time.replace(tzinfo=timezone.utc) == start_time
    assert rec.target_soc == 80.0
    assert rec.recommendation_message == "Hold at 80% SoC until morning top-off."
    assert rec.user.id == user.id
    assert rec.session.id == session.id
    assert len(user.recommendations) == 1
    assert len(session.recommendations) == 1


def test_cascade_delete(db_session):
    """Test that deleting a user cascades to all related entities."""
    user = User(name="Frank", email="frank@example.com")
    db_session.add(user)
    db_session.commit()

    session = ChargingSession(
        user_id=user.id,
        start_time=datetime.now(timezone.utc),
        start_battery_percent=30.0,
    )
    reading = BatteryReading(
        user_id=user.id,
        voltage=3.9,
        current=1.2,
        temperature=25.0,
        battery_percent=40.0,
    )
    prediction = Prediction(
        user_id=user.id,
        predicted_unplug_time=datetime.now(timezone.utc) + timedelta(hours=5),
        confidence_score=0.85,
    )
    db_session.add_all([session, reading, prediction])
    db_session.commit()

    rec = Recommendation(
        user_id=user.id,
        session_id=session.id,
        predicted_unplug_time=datetime.now(timezone.utc) + timedelta(hours=5),
        recommended_start_time=datetime.now(timezone.utc) + timedelta(hours=4),
        target_soc=80.0,
    )
    db_session.add(rec)
    db_session.commit()

    # Verify entities exist
    assert db_session.query(ChargingSession).filter_by(user_id=user.id).count() == 1
    assert db_session.query(BatteryReading).filter_by(user_id=user.id).count() == 1
    assert db_session.query(Prediction).filter_by(user_id=user.id).count() == 1
    assert db_session.query(Recommendation).filter_by(user_id=user.id).count() == 1

    # Delete user
    db_session.delete(user)
    db_session.commit()

    # Verify cascades
    assert db_session.query(ChargingSession).filter_by(user_id=user.id).count() == 0
    assert db_session.query(BatteryReading).filter_by(user_id=user.id).count() == 0
    assert db_session.query(Prediction).filter_by(user_id=user.id).count() == 0
    assert db_session.query(Recommendation).filter_by(user_id=user.id).count() == 0
