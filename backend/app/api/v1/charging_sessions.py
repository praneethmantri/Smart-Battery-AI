import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.charging_session import ChargingSession
from app.models.recommendation import Recommendation
from app.schemas.charging_session import (
    ChargingSessionCreate,
    ChargingSessionResponse,
)
from app.services.optimizer import optimizer_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=ChargingSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a charging session",
)
def create_charging_session(
    payload: ChargingSessionCreate,
    db: Session = Depends(get_db),
):
    """
    Creates a new charging session event for a user.
    Validates user existence and battery percentage bounds.
    """
    if payload.start_battery_percent is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_battery_percent is required",
        )

    # Validate user existence
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        logger.warning("Attempt to create session for non-existent user: %d", payload.user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {payload.user_id} not found",
        )

    start_dt = payload.start_time or datetime.now(timezone.utc)
    day_of_week = payload.day_of_week if payload.day_of_week is not None else start_dt.weekday()

    session = ChargingSession(
        user_id=user.id,
        start_time=start_dt,
        end_time=payload.end_time,
        start_battery_percent=payload.start_battery_percent,
        end_battery_percent=payload.end_battery_percent,
        average_temperature=payload.average_temperature,
        charging_duration_minutes=payload.charging_duration_minutes,
        charger_type=payload.charger_type,
        screen_usage_minutes=payload.screen_usage_minutes or 0.0,
        idle_usage_minutes=payload.idle_usage_minutes or 0.0,
        previous_day_usage_minutes=payload.previous_day_usage_minutes or 0.0,
        day_of_week=day_of_week,
        data_source=payload.data_source or "SYNTHETIC",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # If session is active (no end_time), generate and record initial recommendation plan
    if session.end_time is None:
        try:
            predicted_unplug, plan = optimizer_service.generate_charging_plan(
                user_id=str(user.id),
                plug_time=start_dt,
                start_battery_pct=payload.start_battery_percent,
                target_battery_pct=payload.target_battery_pct,
            )
            rec = Recommendation(
                user_id=user.id,
                session_id=session.id,
                predicted_unplug_time=predicted_unplug,
                recommended_start_time=plan.phase_2_topoff_start or start_dt,
                target_soc=plan.hold_at_pct,
                recommendation_message=plan.recommendation_message,
                mode=plan.mode,
                phase_1_fast_charge_until=plan.phase_1_fast_charge_until,
                hold_at_pct=plan.hold_at_pct,
                phase_2_topoff_start=plan.phase_2_topoff_start,
                confidence_score=plan.confidence_score,
            )
            db.add(rec)
            db.commit()
        except Exception as exc:
            logger.error("Failed to generate recommendation for session %d: %s", session.id, str(exc))

    logger.info("Charging session created: id=%d for user=%d", session.id, user.id)
    return session


@router.get(
    "/{user_id}",
    response_model=List[ChargingSessionResponse],
    summary="Get charging sessions for a user",
)
def get_user_charging_sessions(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    data_source: Optional[str] = Query(None, description="Filter by data source: REAL_WINDOWS, SYNTHETIC, MANUAL"),
    db: Session = Depends(get_db),
):
    """
    Returns historical charging sessions for the given user ID,
    ordered by start_time in descending order.
    """
    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID must be a positive integer",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    query = db.query(ChargingSession).filter(ChargingSession.user_id == user_id)
    if data_source:
        query = query.filter(ChargingSession.data_source == data_source)

    sessions = (
        query
        .order_by(ChargingSession.start_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return sessions


@router.get(
    "/{user_id}/latest",
    response_model=ChargingSessionResponse,
    summary="Get latest charging session for a user",
)
def get_latest_charging_session(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Returns the most recent charging session for the specified user."""
    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID must be a positive integer",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    latest = (
        db.query(ChargingSession)
        .filter(ChargingSession.user_id == user_id)
        .order_by(ChargingSession.start_time.desc())
        .first()
    )
    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No charging sessions found for user {user_id}",
        )
    return latest
