import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.battery_reading import BatteryReading
from app.schemas.battery_reading import (
    BatteryReadingCreate,
    BatteryReadingResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=BatteryReadingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest battery telemetry reading",
)
def create_battery_reading(
    payload: BatteryReadingCreate,
    db: Session = Depends(get_db),
):
    """
    Ingests live battery telemetry (voltage, current, temperature, SoC).
    Validates user existence and numerical bounds.
    """
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        logger.warning("Battery reading rejected: user %d not found", payload.user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {payload.user_id} not found",
        )

    reading = BatteryReading(
        user_id=user.id,
        timestamp=payload.timestamp or datetime.now(timezone.utc),
        voltage=payload.voltage,
        current=payload.current,
        temperature=payload.temperature,
        battery_percent=payload.battery_percent,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    logger.debug("Battery reading recorded: id=%d for user=%d", reading.id, user.id)
    return reading


@router.get(
    "/{user_id}",
    response_model=List[BatteryReadingResponse],
    summary="Get battery readings for a user",
)
def get_user_battery_readings(
    user_id: int,
    order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order by timestamp"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Returns battery telemetry readings for a user, ordered by timestamp.
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

    query = db.query(BatteryReading).filter(BatteryReading.user_id == user_id)
    if order == "asc":
        query = query.order_by(BatteryReading.timestamp.asc())
    else:
        query = query.order_by(BatteryReading.timestamp.desc())

    readings = query.offset(offset).limit(limit).all()
    return readings


@router.get(
    "/{user_id}/latest",
    response_model=BatteryReadingResponse,
    summary="Get latest battery reading for a user",
)
def get_latest_battery_reading(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Returns the most recent battery reading for the given user."""
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
        db.query(BatteryReading)
        .filter(BatteryReading.user_id == user_id)
        .order_by(BatteryReading.timestamp.desc())
        .first()
    )
    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No battery readings found for user {user_id}",
        )
    return latest
