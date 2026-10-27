from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_serializer


class ChargingSessionBase(BaseModel):
    user_id: int = Field(..., gt=0, description="ID of the user")
    start_time: datetime = Field(..., description="Timestamp when device was plugged in")
    start_battery_percent: float = Field(..., ge=0.0, le=100.0, description="Battery percentage at plug-in")
    end_time: Optional[datetime] = Field(None, description="Timestamp when device was unplugged")
    end_battery_percent: Optional[float] = Field(None, ge=0.0, le=100.0, description="Battery percentage at unplug")
    average_temperature: Optional[float] = Field(None, description="Average temperature during session")
    charging_duration_minutes: Optional[float] = Field(None, ge=0.0, description="Charging duration in minutes")
    charger_type: str = Field("standard_ac", description="Charger type")
    screen_usage_minutes: Optional[float] = Field(0.0, ge=0.0, description="Screen on time during charging")
    idle_usage_minutes: Optional[float] = Field(0.0, ge=0.0, description="System idle time during charging")
    previous_day_usage_minutes: Optional[float] = Field(0.0, ge=0.0, description="Aggregate usage from prior day")
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="Day of week (0=Mon, 6=Sun)")
    data_source: Optional[str] = Field("SYNTHETIC", description="Source of session: REAL_WINDOWS, SYNTHETIC, or MANUAL")


class ChargingSessionCreate(BaseModel):
    user_id: int = Field(..., gt=0, description="ID of the user")
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    start_battery_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    end_battery_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    average_temperature: Optional[float] = None
    charging_duration_minutes: Optional[float] = Field(None, ge=0.0)
    charger_type: str = Field("standard_ac", description="Charger type")
    screen_usage_minutes: Optional[float] = Field(0.0, ge=0.0)
    idle_usage_minutes: Optional[float] = Field(0.0, ge=0.0)
    previous_day_usage_minutes: Optional[float] = Field(0.0, ge=0.0)
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    data_source: Optional[str] = Field("SYNTHETIC", description="REAL_WINDOWS, SYNTHETIC, or MANUAL")
    target_battery_pct: float = Field(100.0, ge=20.0, le=100.0)

    # Backward compatibility aliases
    plug_time: Optional[datetime] = None
    unplug_time: Optional[datetime] = None
    start_battery_pct: Optional[float] = None
    end_battery_pct: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def reconcile_aliases(cls, data):
        if isinstance(data, dict):
            # start_time / plug_time
            if "start_time" not in data and "plug_time" in data:
                data["start_time"] = data["plug_time"]
            if not data.get("start_time"):
                data["start_time"] = datetime.now(timezone.utc)

            # end_time / unplug_time
            if "end_time" not in data and "unplug_time" in data:
                data["end_time"] = data["unplug_time"]

            # battery percents
            if "start_battery_percent" not in data and "start_battery_pct" in data:
                data["start_battery_percent"] = data["start_battery_pct"]
            if "end_battery_percent" not in data and "end_battery_pct" in data:
                data["end_battery_percent"] = data["end_battery_pct"]

            # day of week auto-derivation
            if data.get("day_of_week") is None and data.get("start_time"):
                try:
                    if isinstance(data["start_time"], str):
                        dt = datetime.fromisoformat(data["start_time"])
                        data["day_of_week"] = dt.weekday()
                    elif isinstance(data["start_time"], datetime):
                        data["day_of_week"] = data["start_time"].weekday()
                except Exception:
                    pass

            # calculate duration if end_time and start_time given and duration is None
            if data.get("charging_duration_minutes") is None and data.get("start_time") and data.get("end_time"):
                try:
                    st = datetime.fromisoformat(data["start_time"]) if isinstance(data["start_time"], str) else data["start_time"]
                    et = datetime.fromisoformat(data["end_time"]) if isinstance(data["end_time"], str) else data["end_time"]
                    dur = (et - st).total_seconds() / 60.0
                    data["charging_duration_minutes"] = max(0.0, round(dur, 2))
                except Exception:
                    pass

        return data


class ChargingSessionEnd(BaseModel):
    unplug_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    end_battery_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    end_battery_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    average_temperature: Optional[float] = None
    screen_usage_minutes: Optional[float] = Field(None, ge=0.0)

    @model_validator(mode="before")
    @classmethod
    def reconcile_end_aliases(cls, data):
        if isinstance(data, dict):
            if "end_time" not in data and "unplug_time" in data:
                data["end_time"] = data["unplug_time"]
            if "end_battery_percent" not in data and "end_battery_pct" in data:
                data["end_battery_percent"] = data["end_battery_pct"]
        return data


class ChargingSessionResponse(ChargingSessionBase):
    id: int
    created_at: datetime

    # Aliases for response consumers
    @property
    def plug_time(self) -> datetime:
        return self.start_time

    @property
    def unplug_time(self) -> Optional[datetime]:
        return self.end_time

    @property
    def start_battery_pct(self) -> float:
        return self.start_battery_percent

    @property
    def end_battery_pct(self) -> Optional[float]:
        return self.end_battery_percent

    @property
    def duration_minutes(self) -> Optional[float]:
        return self.charging_duration_minutes

    @field_serializer("start_time", "end_time", "created_at", when_used="json")
    def serialize_utc_datetimes(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    model_config = ConfigDict(from_attributes=True)


class SessionListResponse(BaseModel):
    total: int
    sessions: List[ChargingSessionResponse]
