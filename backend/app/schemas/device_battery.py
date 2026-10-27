from typing import Optional
from pydantic import BaseModel, Field


class DeviceBatteryResponse(BaseModel):
    """
    Schema representing local hardware device battery telemetry.
    Used for local development and live laptop demonstrations.
    """
    available: bool = Field(..., description="Whether a local physical hardware battery was detected")
    battery_percent: Optional[float] = Field(None, description="Current hardware battery State of Charge (0-100%)")
    is_plugged_in: Optional[bool] = Field(None, description="Whether the device is currently connected to AC power")
    seconds_left: Optional[int] = Field(None, description="Estimated battery discharge seconds remaining, if available")
    source: str = Field(..., description="Source origin of the battery reading (e.g. WINDOWS_SYSTEM or UNAVAILABLE)")
    timestamp: str = Field(..., description="ISO 8601 timestamp of sensor sample")
