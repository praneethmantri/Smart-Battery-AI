from datetime import datetime, timezone, timedelta
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.recommendation import Recommendation
from app.schemas.recommendation import (
    RecommendationResponse,
    SmartRecommendationRequest,
    SmartRecommendationResponse,
    PredictionSummary,
    RecommendationDetail,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{user_id}",
    response_model=List[RecommendationResponse],
    summary="Get charging recommendations for a user",
)
def get_user_recommendations(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Returns historical charging recommendations for the specified user,
    ordered by creation timestamp descending.
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

    recs = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == user_id)
        .order_by(Recommendation.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return recs


@router.get(
    "/{user_id}/latest",
    response_model=RecommendationResponse,
    summary="Get latest charging recommendation for a user",
)
def get_latest_recommendation(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Returns the most recent charging recommendation for a user. Returns 404 if none found."""
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
        db.query(Recommendation)
        .filter(Recommendation.user_id == user_id)
        .order_by(Recommendation.created_at.desc())
        .first()
    )
    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No recommendations found for user {user_id}",
        )
    return latest


@router.post(
    "/{user_id}/generate",
    response_model=SmartRecommendationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate personalized charging recommendation",
    description=(
        "Executes the full intelligent battery optimization workflow: "
        "1. Validates user existence and battery limits. "
        "2. Loads historical completed sessions from the database. "
        "3. Computes leak-free features and runs ML prediction (GLOBAL_BASELINE, BLENDED, or PERSONALIZED). "
        "4. Solves optimal charging schedule via Recommendation Engine. "
        "5. Persists Prediction and Recommendation records in the database. "
        "6. Returns coupled prediction and personalized recommendation response."
    ),
    responses={
        201: {"description": "Recommendation generated and persisted successfully."},
        400: {"description": "Invalid input parameters (e.g. invalid battery percentage, SOC bounds)."},
        404: {"description": "User not found."},
        500: {"description": "Internal optimization or inference failure."},
    },
)
def generate_user_recommendation(
    user_id: int,
    payload: SmartRecommendationRequest,
    db: Session = Depends(get_db),
):
    """
    POST /api/recommendations/{user_id}/generate
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

    # Validate battery percentages & bounds
    current_soc = payload.current_battery_percent
    if not (0.0 <= current_soc <= 100.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"current_battery_percent must be between 0.0 and 100.0, got: {current_soc}",
        )

    min_required_soc = payload.minimum_required_soc if payload.minimum_required_soc is not None else 70.0
    target_soc = 100.0 if payload.wants_full_charge else (payload.preferred_target_soc if payload.preferred_target_soc is not None else 80.0)

    if target_soc < min_required_soc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"preferred_target_soc ({target_soc}%) cannot be less than minimum_required_soc ({min_required_soc}%)",
        )

    if not (20.0 <= target_soc <= 100.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"target SOC must be between 20.0% and 100.0%, got: {target_soc}",
        )

    if payload.estimated_charging_rate_percent_per_hour is not None and payload.estimated_charging_rate_percent_per_hour <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"estimated_charging_rate_percent_per_hour must be strictly positive, got: {payload.estimated_charging_rate_percent_per_hour}",
        )

    if payload.current_temperature is not None and (payload.current_temperature < -40.0 or payload.current_temperature > 90.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unrealistic temperature reading: {payload.current_temperature}°C",
        )

    plug_time = payload.plug_time or datetime.now(timezone.utc)
    if plug_time.tzinfo is None:
        plug_time = plug_time.replace(tzinfo=timezone.utc)

    # 1. Fetch user's completed charging sessions
    from app.models.charging_session import ChargingSession
    from app.models.prediction import Prediction
    from app.services.ml_service import ml_service
    from app.services.recommendation_engine import recommendation_engine, RecommendationConfig
    from app.schemas.recommendation import RecommendationRequest, RecommendationMode

    history_sessions = (
        db.query(ChargingSession)
        .filter(ChargingSession.user_id == user_id)
        .order_by(ChargingSession.start_time.asc())
        .all()
    )

    # 2. Run ML Prediction
    try:
        pred_result = ml_service.predict(
            user_id=user.id,
            plug_time=plug_time,
            start_battery_pct=current_soc,
            charger_type=payload.charger_type or "standard",
            history_sessions=history_sessions,
        )
    except Exception as exc:
        logger.error("Prediction failed during recommendation generation for user %d: %s", user.id, str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate expected unplug time prediction.",
        )

    # 3. Generate Personalized Recommendation
    try:
        rec_req = RecommendationRequest(
            user_id=user.id,
            current_battery_percent=current_soc,
            target_battery_percent=target_soc,
            plug_time=plug_time,
            current_temperature=payload.current_temperature,
            charger_type=payload.charger_type or "standard",
            prediction_override=pred_result.predicted_unplug_datetime,
            confidence_score_override=pred_result.confidence_score,
        )

        rec_out = recommendation_engine.generate_recommendation(
            request=rec_req,
            history_count=pred_result.history_count,
            circular_std=pred_result.circular_std,
            is_irregular=(pred_result.circular_std >= 1.5),
        )

        # Handle user preference disallowing delay
        if payload.allow_delayed_charging is False and rec_out.mode in [RecommendationMode.DELAYED_CHARGE.value, RecommendationMode.CONSERVATIVE_CHARGE.value]:
            rec_out.mode = RecommendationMode.CHARGE_NOW.value
            rec_out.recommended_start_time = plug_time
            rec_out.estimated_finish_time = plug_time + timedelta(minutes=rec_out.estimated_charging_minutes)
            rec_out.reason = "Delayed charging disabled by user preference. Immediate continuous charging scheduled."
            rec_out.recommendation_message = (
                f"Start charging immediately: Continuous charging to {target_soc:.0f}% recommended "
                f"per user preference (ready by {rec_out.estimated_finish_time.strftime('%H:%M')})."
            )

    except Exception as rec_exc:
        logger.error("Recommendation generation failed for user %d: %s", user.id, str(rec_exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recommendation engine failed to compute charging schedule.",
        )

    # 4. Persist Prediction and Recommendation in Database
    try:
        pred_record = Prediction(
            user_id=user.id,
            predicted_unplug_time=pred_result.predicted_unplug_datetime,
            confidence_score=pred_result.confidence_score,
            model_version=pred_result.model_version,
            created_at=datetime.now(timezone.utc),
        )
        db.add(pred_record)

        rec_record = Recommendation(
            user_id=user.id,
            predicted_unplug_time=pred_result.predicted_unplug_datetime,
            recommended_start_time=rec_out.recommended_start_time,
            target_soc=rec_out.target_soc,
            recommendation_message=rec_out.recommendation_message,
            mode=rec_out.mode,
            confidence_score=rec_out.confidence_score,
            phase_1_fast_charge_until=rec_out.estimated_finish_time if rec_out.mode == RecommendationMode.CHARGE_NOW.value else None,
            hold_at_pct=rec_out.target_soc,
            phase_2_topoff_start=rec_out.recommended_start_time if rec_out.mode != RecommendationMode.CHARGE_NOW.value else None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(rec_record)
        db.commit()
        db.refresh(pred_record)
        db.refresh(rec_record)
    except Exception as db_exc:
        db.rollback()
        logger.error("Failed to persist prediction/recommendation records: %s", str(db_exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database failure while persisting recommendation.",
        )

    logger.info(
        "Smart recommendation generated for user %d: rec_id=%d | pred_id=%d | mode=%s | start=%s | finish=%s",
        user.id, rec_record.id, pred_record.id, rec_out.mode,
        rec_out.recommended_start_time.strftime('%H:%M'), rec_out.estimated_finish_time.strftime('%H:%M')
    )

    from app.schemas.recommendation import (
        PredictionSummary,
        RecommendationDetail,
        SmartRecommendationResponse,
    )

    return SmartRecommendationResponse(
        user_id=user.id,
        prediction=PredictionSummary(
            predicted_unplug_time=pred_result.predicted_unplug_time_str,
            prediction_source=pred_result.prediction_source,
            confidence_level=pred_result.confidence_level,
            confidence_score=pred_result.confidence_score,
            history_count=pred_result.history_count,
            predicted_unplug_datetime=pred_result.predicted_unplug_datetime,
        ),
        recommendation=RecommendationDetail(
            mode=rec_out.mode,
            current_soc=rec_out.current_soc,
            target_soc=rec_out.target_soc,
            recommended_start_time=rec_out.recommended_start_time.strftime("%H:%M"),
            estimated_finish_time=rec_out.estimated_finish_time.strftime("%H:%M"),
            estimated_charging_minutes=rec_out.estimated_charging_minutes,
            message=rec_out.recommendation_message,
            reason=rec_out.reason,
            warnings=rec_out.warnings,
            recommended_start_datetime=rec_out.recommended_start_time,
            estimated_finish_datetime=rec_out.estimated_finish_time,
        ),
        recommendation_id=rec_record.id,
        prediction_id=pred_record.id,
        created_at=rec_record.created_at,
    )
