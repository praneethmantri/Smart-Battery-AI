from datetime import datetime, timezone
import os
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.services.ml_service import ml_service

router = APIRouter()


@router.get("", summary="Check API & Service Health")
def check_health(db: Session = Depends(get_db)):
    """Health check endpoint validating database connectivity and ML artifact status."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unhealthy: {str(exc)}"

    model_health = ml_service.get_health_status()
    is_healthy = (db_status == "connected" and model_health.get("global_model") == "loaded")

    return {
        "status": "healthy" if is_healthy else "degraded",
        "database": db_status,
        "global_model": model_health.get("global_model", "unavailable"),
        "personalized_model": model_health.get("personalized_model", "unavailable"),
        "ml_model_loaded": (model_health.get("global_model") == "loaded") or os.path.exists(settings.ML_MODEL_PATH),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
