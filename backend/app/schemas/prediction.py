from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class PredictionBase(BaseModel):
    user_id: int = Field(..., description="ID of the user")
    predicted_unplug_time: datetime = Field(..., description="Estimated unplug time")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence level (0 to 1)")
    model_version: str = Field("1.0.0", description="Version of the ML model used")


class PredictionCreate(PredictionBase):
    pass


class PredictionResponse(PredictionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PredictionRequest(BaseModel):
    """Optional payload when requesting an on-demand unplug prediction."""
    plug_time: Optional[datetime] = Field(None, description="Plug-in event timestamp (defaults to current time)")
    current_battery_percent: Optional[float] = Field(50.0, ge=0.0, le=100.0, description="Battery percentage at plug-in")
    charger_type: Optional[str] = Field("standard", description="Charger type: 'slow', 'standard', 'fast'")
    previous_day_usage_minutes: Optional[float] = Field(None, ge=0.0, description="Prior day usage in minutes")


class PredictionResultResponse(BaseModel):
    """Structured response returned by POST /api/predict/{user_id}."""
    user_id: int = Field(..., description="ID of the user")
    predicted_unplug_time: str = Field(..., description="Formatted unplug clock time (HH:MM)")
    predicted_unplug_hour: float = Field(..., description="Continuous hour of day [0.0, 24.0)")
    prediction_source: str = Field(..., description="Prediction strategy: GLOBAL_BASELINE, BLENDED, PERSONALIZED, RULE_BASED")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score [0.0, 1.0]")
    confidence_level: str = Field(..., description="Confidence rating: HIGH, MEDIUM, LOW")
    history_count: int = Field(..., description="Number of completed historical sessions evaluated")
    model_version: str = Field(..., description="ML model artifact version")
    created_at: datetime = Field(..., description="Prediction persistence timestamp")
    predicted_unplug_datetime: Optional[datetime] = Field(None, description="Full future unplug datetime")
    prediction_id: Optional[int] = Field(None, description="Persisted prediction ID")

