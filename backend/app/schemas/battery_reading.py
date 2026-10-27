from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class BatteryReadingBase(BaseModel):
    user_id: int = Field(..., gt=0, description="ID of the user")
    timestamp: datetime = Field(..., description="Time of telemetry reading")
    voltage: float = Field(..., description="Battery voltage in Volts")
    current: float = Field(..., description="Battery current in Amperes")
    temperature: float = Field(..., description="Battery temperature in Celsius")
    battery_percent: float = Field(..., ge=0.0, le=100.0, description="Battery State of Charge (0-100%)")


class BatteryReadingCreate(BaseModel):
    user_id: int = Field(..., gt=0, description="ID of the user")
    timestamp: Optional[datetime] = None
    voltage: float = Field(..., description="Battery voltage in Volts")
    current: float = Field(..., description="Battery current in Amperes")
    temperature: float = Field(..., description="Battery temperature in Celsius")
    battery_percent: float = Field(..., ge=0.0, le=100.0, description="Battery State of Charge (0-100%)")

    @model_validator(mode="before")
    @classmethod
    def set_default_timestamp(cls, data):
        if isinstance(data, dict):
            if "timestamp" not in data or data["timestamp"] is None:
                data["timestamp"] = datetime.now(timezone.utc)
        return data


class BatteryReadingResponse(BatteryReadingBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
