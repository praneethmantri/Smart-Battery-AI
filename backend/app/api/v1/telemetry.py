import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.charging_session import ChargingSession
from app.models.telemetry_sample import TelemetrySample
from app.schemas.charging_session import ChargingSessionResponse
from app.schemas.telemetry import (
    TelemetryStatusResponse,
    TelemetrySampleResponse,
    TelemetryPollNowResponse,
)
from app.services.telemetry_service import telemetry_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/status",
    response_model=TelemetryStatusResponse,
    summary="Get background telemetry and learning status",
    description="Returns live Windows battery readings, active charging session, real sessions count, and personalization progress.",
)
def get_telemetry_status(
    user_id: int = Query(1, gt=0, description="Target user ID"),
    db: Session = Depends(get_db),
):
    telemetry_service.target_user_id = user_id
    status_data = telemetry_service.get_status(db=db)
    return status_data


@router.get(
    "/sessions",
    response_model=List[ChargingSessionResponse],
    summary="Get real Windows charging sessions",
    description="Returns list of actual recorded sessions tagged REAL_WINDOWS.",
)
def get_real_charging_sessions(
    user_id: int = Query(1, gt=0, description="User ID"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(ChargingSession)
        .filter(
            ChargingSession.user_id == user_id,
            ChargingSession.data_source == "REAL_WINDOWS",
        )
        .order_by(ChargingSession.start_time.desc())
        .limit(limit)
        .all()
    )
    return sessions


@router.get(
    "/samples",
    response_model=List[TelemetrySampleResponse],
    summary="Get recent telemetry samples",
    description="Returns periodic battery and user activity telemetry samples recorded by the background collector.",
)
def get_telemetry_samples(
    user_id: int = Query(1, gt=0, description="User ID"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    samples = (
        db.query(TelemetrySample)
        .filter(TelemetrySample.user_id == user_id)
        .order_by(TelemetrySample.timestamp.desc())
        .limit(limit)
        .all()
    )
    return samples


@router.post(
    "/poll-now",
    response_model=TelemetryPollNowResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger immediate telemetry poll",
    description="Forces a single polling cycle to sample hardware battery and evaluate charging transitions immediately.",
)
def trigger_poll_now(
    user_id: int = Query(1, gt=0, description="Target user ID"),
    db: Session = Depends(get_db),
):
    telemetry_service.target_user_id = user_id
    res = telemetry_service.poll_once(db=db)

    sample_obj = None
    if res.get("sample_id"):
        sample_obj = db.query(TelemetrySample).filter(TelemetrySample.id == res["sample_id"]).first()

    return TelemetryPollNowResponse(
        success=res.get("success", False),
        message="Telemetry poll completed successfully" if res.get("success") else f"Poll failed: {res.get('error')}",
        sample=sample_obj,
        transition_event=res.get("transition_event"),
    )
