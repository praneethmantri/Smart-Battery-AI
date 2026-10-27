from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.charging_session import ChargingSession
from app.models.recommendation import Recommendation
from app.schemas.charging_session import (
    ChargingSessionCreate,
    ChargingSessionResponse,
    ChargingSessionEnd,
    SessionListResponse,
)
from app.schemas.recommendation import (
    RecommendationResponse,
    CurrentStatusResponse,
)
from app.services.optimizer import optimizer_service

router = APIRouter()


@router.post(
    "/sessions",
    response_model=RecommendationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start charging session and get AI schedule",
)
def start_session(
    payload: ChargingSessionCreate,
    db: Session = Depends(get_db),
):
    """
    Ingests plug-in event, computes ML predicted unplug time,
    determines the optimal delayed charging schedule, and persists the session.
    """
    # Ensure user exists in database or auto-provision
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        user = User(
            id=payload.user_id,
            name=f"User {payload.user_id}",
            email=f"user_{payload.user_id}@example.com",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    start_dt = payload.start_time or payload.plug_time or datetime.now(timezone.utc)
    start_pct = (
        payload.start_battery_percent
        if payload.start_battery_percent is not None
        else (payload.start_battery_pct if payload.start_battery_pct is not None else 50.0)
    )

    # 1. Generate optimized charging recommendation
    predicted_unplug, plan = optimizer_service.generate_charging_plan(
        user_id=str(payload.user_id),
        plug_time=start_dt,
        start_battery_pct=start_pct,
        target_battery_pct=payload.target_battery_pct,
    )

    # 2. Persist session
    new_session = ChargingSession(
        user_id=user.id,
        start_time=start_dt,
        start_battery_percent=start_pct,
        charger_type=payload.charger_type,
        screen_usage_minutes=payload.screen_usage_minutes or 0.0,
        average_temperature=payload.average_temperature,
        day_of_week=payload.day_of_week if payload.day_of_week is not None else start_dt.weekday(),
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    # 3. Persist recommendation
    rec_record = Recommendation(
        session_id=new_session.id,
        user_id=user.id,
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
    db.add(rec_record)
    db.commit()
    db.refresh(rec_record)

    return RecommendationResponse(
        id=rec_record.id,
        session_id=new_session.id,
        user_id=user.id,
        predicted_unplug_time=predicted_unplug,
        recommended_start_time=rec_record.recommended_start_time,
        target_soc=rec_record.target_soc,
        recommendation_message=rec_record.recommendation_message,
        created_at=rec_record.created_at,
        recommendation=plan,
    )


@router.post(
    "/sessions/{session_id}/end",
    response_model=ChargingSessionResponse,
    summary="End charging session (unplug event)",
)
def end_session(
    session_id: int,
    payload: ChargingSessionEnd,
    db: Session = Depends(get_db),
):
    """Updates charging session when the device is unplugged."""
    session = db.query(ChargingSession).filter(ChargingSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found",
        )

    end_dt = payload.end_time or payload.unplug_time or datetime.now(timezone.utc)
    end_pct = (
        payload.end_battery_percent
        if payload.end_battery_percent is not None
        else (payload.end_battery_pct if payload.end_battery_pct is not None else 100.0)
    )

    session.end_time = end_dt
    session.end_battery_percent = end_pct

    if payload.average_temperature is not None:
        session.average_temperature = payload.average_temperature
    if payload.screen_usage_minutes is not None:
        session.screen_usage_minutes = payload.screen_usage_minutes

    # Calculate duration in minutes
    start_with_tz = session.start_time.replace(tzinfo=end_dt.tzinfo)
    duration = (end_dt - start_with_tz).total_seconds() / 60.0
    session.charging_duration_minutes = max(0.0, round(duration, 2))

    db.commit()
    db.refresh(session)
    return session


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="List charging sessions",
)
def list_sessions(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Fetches historical charging sessions."""
    query = db.query(ChargingSession)
    if user_id is not None:
        query = query.filter(ChargingSession.user_id == user_id)

    total = query.count()
    sessions = query.order_by(ChargingSession.start_time.desc()).offset(offset).limit(limit).all()

    return SessionListResponse(total=total, sessions=sessions)


@router.get(
    "/status",
    response_model=CurrentStatusResponse,
    summary="Get current charging and recommendation status",
)
def get_current_status(
    user_id: int = Query(..., description="User ID to inspect"),
    db: Session = Depends(get_db),
):
    """Provides current active session phase and next scheduled transition."""
    latest_session = (
        db.query(ChargingSession)
        .filter(ChargingSession.user_id == user_id, ChargingSession.end_time.is_(None))
        .order_by(ChargingSession.start_time.desc())
        .first()
    )

    if not latest_session:
        return CurrentStatusResponse(
            user_id=user_id,
            active_session=False,
            current_phase="idle_unplugged",
            current_battery_pct=100.0,
            next_transition_time=None,
            predicted_unplug_time=None,
        )

    latest_rec = (
        db.query(Recommendation)
        .filter(Recommendation.session_id == latest_session.id)
        .order_by(Recommendation.created_at.desc())
        .first()
    )

    now = datetime.now(timezone.utc)
    current_phase = "fast_charging"
    next_transition = None

    if latest_rec:
        rec_fast_until = (
            latest_rec.phase_1_fast_charge_until.replace(tzinfo=timezone.utc)
            if latest_rec.phase_1_fast_charge_until
            else None
        )
        rec_topoff_start = (
            latest_rec.phase_2_topoff_start.replace(tzinfo=timezone.utc)
            if latest_rec.phase_2_topoff_start
            else None
        )

        if rec_fast_until and now < rec_fast_until:
            current_phase = "fast_charging_to_80"
            next_transition = rec_fast_until
        elif rec_topoff_start and now < rec_topoff_start:
            current_phase = "holding_at_80"
            next_transition = rec_topoff_start
        else:
            current_phase = "topping_off_to_100"
            next_transition = latest_rec.predicted_unplug_time

    return CurrentStatusResponse(
        user_id=user_id,
        active_session=True,
        current_phase=current_phase,
        current_battery_pct=latest_session.start_battery_percent,
        next_transition_time=next_transition,
        predicted_unplug_time=latest_rec.predicted_unplug_time if latest_rec else None,
    )
