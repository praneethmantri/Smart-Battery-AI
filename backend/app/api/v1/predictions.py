from datetime import datetime, timezone
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.prediction import Prediction
from app.schemas.prediction import (
    PredictionResponse,
    PredictionRequest,
    PredictionResultResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{user_id}",
    response_model=List[PredictionResponse],
    summary="Get predictions for a user",
)
def get_user_predictions(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Returns previous ML predictions for the specified user,
    ordered by creation timestamp in descending order.
    Returns an empty list if no predictions exist yet.
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

    predictions = (
        db.query(Prediction)
        .filter(Prediction.user_id == user_id)
        .order_by(Prediction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return predictions


@router.get(
    "/{user_id}/latest",
    response_model=PredictionResponse,
    summary="Get latest prediction for a user",
)
def get_latest_prediction(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Returns the most recent prediction for a user. Returns 404 if none found."""
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
        db.query(Prediction)
        .filter(Prediction.user_id == user_id)
        .order_by(Prediction.created_at.desc())
        .first()
    )
    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No predictions found for user {user_id}",
        )
    return latest


@router.post(
    "/{user_id}",
    response_model=PredictionResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate unplug-time prediction for a user",
    description=(
        "Executes intelligent ML unplug-time inference for the given user. "
        "Loads historical completed sessions from the database, extracts strictly leak-free "
        "cyclical features, and dynamically engages the optimal strategy: "
        "GLOBAL_BASELINE (0-2 sessions), BLENDED (3-6 sessions), or PERSONALIZED (7+ sessions). "
        "Stores the resulting prediction in the database and returns structured metadata."
    ),
    responses={
        201: {"description": "Prediction generated and persisted successfully."},
        400: {"description": "Invalid input parameters (e.g. invalid battery percentage or user ID)."},
        404: {"description": "User not found."},
        500: {"description": "Internal prediction service failure."},
    },
)
def create_user_prediction(
    user_id: int,
    payload: Optional[PredictionRequest] = None,
    db: Session = Depends(get_db),
):
    """
    POST /api/predict/{user_id} and POST /api/predictions/{user_id}
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

    # Parse and validate request parameters
    req = payload or PredictionRequest()
    current_soc = req.current_battery_percent if req.current_battery_percent is not None else 50.0
    if not (0.0 <= current_soc <= 100.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"current_battery_percent must be between 0.0 and 100.0, got: {current_soc}",
        )

    plug_time = req.plug_time or datetime.now(timezone.utc)
    if plug_time.tzinfo is None:
        plug_time = plug_time.replace(tzinfo=timezone.utc)

    # Fetch user's completed charging sessions from database
    from app.models.charging_session import ChargingSession
    from app.services.ml_service import ml_service

    history_sessions = (
        db.query(ChargingSession)
        .filter(ChargingSession.user_id == user_id)
        .order_by(ChargingSession.start_time.asc())
        .all()
    )

    logger.info(
        "Prediction requested for user %d | Historical sessions in DB: %d | Start SOC: %.1f%%",
        user.id, len(history_sessions), current_soc
    )

    try:
        pred_result = ml_service.predict(
            user_id=user.id,
            plug_time=plug_time,
            start_battery_pct=current_soc,
            charger_type=req.charger_type or "standard",
            history_sessions=history_sessions,
            previous_day_usage_minutes=req.previous_day_usage_minutes,
        )
    except Exception as exc:
        logger.error("Inference execution failed for user %d: %s", user.id, str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal prediction service failed to generate an inference result.",
        )

    # Persist prediction record in Prediction database table
    try:
        pred_record = Prediction(
            user_id=user.id,
            predicted_unplug_time=pred_result.predicted_unplug_datetime,
            confidence_score=pred_result.confidence_score,
            model_version=pred_result.model_version,
            created_at=datetime.now(timezone.utc),
        )
        db.add(pred_record)
        db.commit()
        db.refresh(pred_record)
    except Exception as db_exc:
        db.rollback()
        logger.error("Failed to persist prediction record to database: %s", str(db_exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database failure while persisting prediction record.",
        )

    logger.info(
        "Prediction persisted: id=%d | user=%d | unplug=%s | source=%s | conf=%.2f",
        pred_record.id, user.id, pred_result.predicted_unplug_time_str,
        pred_result.prediction_source, pred_result.confidence_score
    )

    return PredictionResultResponse(
        user_id=user.id,
        predicted_unplug_time=pred_result.predicted_unplug_time_str,
        predicted_unplug_hour=pred_result.predicted_unplug_hour,
        prediction_source=pred_result.prediction_source,
        confidence_score=pred_result.confidence_score,
        confidence_level=pred_result.confidence_level,
        history_count=pred_result.history_count,
        model_version=pred_result.model_version,
        created_at=pred_record.created_at,
        predicted_unplug_datetime=pred_result.predicted_unplug_datetime,
        prediction_id=pred_record.id,
    )
