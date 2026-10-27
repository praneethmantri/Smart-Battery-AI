from fastapi import APIRouter
from app.services.device_battery_service import device_battery_service
from app.schemas.device_battery import DeviceBatteryResponse

router = APIRouter()


@router.get(
    "",
    response_model=DeviceBatteryResponse,
    summary="Get real local device battery status",
    description=(
        "Queries local host operating system battery hardware sensor via psutil. "
        "Used for local development, interactive laptop demonstrations, and testing "
        "live battery state of charge (SoC) integration. "
        "Returns available=False if running on a desktop or unsupported system without a battery."
    ),
)
def get_device_battery():
    """
    Returns actual local host battery status:
    - battery_percent: float (0.0 to 100.0)
    - is_plugged_in: bool
    - seconds_left: int or null
    - available: bool
    - source: 'WINDOWS_SYSTEM' or 'UNAVAILABLE'
    """
    return device_battery_service.get_battery_status()
