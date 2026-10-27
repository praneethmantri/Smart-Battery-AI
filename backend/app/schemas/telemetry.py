from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_serializer


class TelemetrySampleBase(BaseModel):
    user_id: int = Field(..., gt=0)
    battery_percent: float = Field(..., ge=0.0, le=100.0)
    is_plugged_in: bool
    seconds_left: Optional[int] = None
    is_user_active: bool = True
    idle_duration_seconds: float = 0.0
    sleep_gap_seconds: float = 0.0
    source: str = "REAL_WINDOWS"


class TelemetrySampleCreate(TelemetrySampleBase):
    timestamp: Optional[datetime] = None


class TelemetrySampleResponse(TelemetrySampleBase):
    id: int
    timestamp: datetime
    created_at: datetime

    @field_serializer("timestamp", "created_at", when_used="json")
    def serialize_utc_datetimes(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    model_config = ConfigDict(from_attributes=True)


class TelemetryStatusResponse(BaseModel):
    collector_running: bool = Field(..., description="Whether background collector is actively polling")
    last_poll_time: Optional[str] = Field(None, description="ISO timestamp of most recent poll")
    poll_interval_seconds: int = Field(120, description="Configured polling interval in seconds")
    user_id: int = Field(1, description="Target user ID")
    device_battery: Dict[str, Any] = Field(default_factory=dict, description="Live OS battery sensor reading")
    active_session: Optional[Dict[str, Any]] = Field(None, description="In-progress charging session metadata if plugged in")
    real_sessions_count: int = Field(0, description="Total completed REAL_WINDOWS sessions in database")
    personalization_stage: str = Field("LEARNING", description="LEARNING (0-2), BLENDED (3-6), or PERSONALIZED (7+)")
    personalization_progress_pct: float = Field(0.0, description="Progress toward full personalization (0-100%)")
    target_sessions_for_full_personalization: int = Field(7, description="Sessions required for full personalization")
    today_active_minutes: float = Field(0.0, description="Aggregate active user time recorded today")
    today_idle_minutes: float = Field(0.0, description="Aggregate idle time recorded today")
    sleep_events_count: int = Field(0, description="Count of detected sleep/suspend periods")
    privacy_notice: str = Field(
        "Telemetry collects only aggregate battery levels and idle durations. "
        "No keystrokes, screen contents, or personal files are recorded.",
        description="Privacy assurance statement"
    )


class TelemetryPollNowResponse(BaseModel):
    success: bool
    message: str
    sample: Optional[TelemetrySampleResponse] = None
    transition_event: Optional[str] = None
