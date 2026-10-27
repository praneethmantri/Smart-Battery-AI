import logging
import platform
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class DeviceBatteryService:
    """
    Service to read real physical host battery telemetry from the operating system
    using psutil (e.g. on Windows laptops).

    Used for local development, pairing live hardware state with ML optimization
    and demo workflows.
    """

    def get_battery_status(self) -> Dict[str, Any]:
        """
        Queries host battery sensors via psutil.sensors_battery().
        Safely handles desktop PCs without battery, OS permission errors,
        and platform-specific exceptions without exposing raw tracebacks.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            import psutil
            battery = psutil.sensors_battery()

            if battery is None:
                logger.info("Host battery sensor returned None (Desktop PC / VM / no battery detected).")
                return {
                    "available": False,
                    "battery_percent": None,
                    "is_plugged_in": None,
                    "seconds_left": None,
                    "source": "UNAVAILABLE",
                    "timestamp": now_iso,
                }

            # psutil secsleft:
            # - psutil.POWER_TIME_UNLIMITED (-2): plugged in and full/not discharging
            # - psutil.POWER_TIME_UNKNOWN (-1): cannot be determined
            # - positive integer: seconds remaining
            secs_left: Optional[int] = None
            if battery.secsleft is not None and battery.secsleft >= 0:
                secs_left = int(battery.secsleft)

            # Determine OS source tag
            sys_name = platform.system().upper()
            source_tag = "WINDOWS_SYSTEM" if sys_name == "WINDOWS" else f"{sys_name}_SYSTEM"

            # Clamp battery percent between 0.0 and 100.0
            percent_val = round(max(0.0, min(100.0, float(battery.percent))), 1)

            logger.debug(
                "Device battery read: %.1f%% | plugged=%s | secsleft=%s | source=%s",
                percent_val, battery.power_plugged, secs_left, source_tag
            )

            return {
                "available": True,
                "battery_percent": percent_val,
                "is_plugged_in": bool(battery.power_plugged) if battery.power_plugged is not None else None,
                "seconds_left": secs_left,
                "source": source_tag,
                "timestamp": now_iso,
            }

        except ImportError as imp_err:
            logger.warning("psutil package not available: %s", str(imp_err))
            return {
                "available": False,
                "battery_percent": None,
                "is_plugged_in": None,
                "seconds_left": None,
                "source": "UNAVAILABLE",
                "timestamp": now_iso,
            }
        except Exception as exc:
            # Catch all OS/sensor/permission errors safely without crashing or exposing tracebacks
            logger.warning("Failed to query hardware battery status: %s", str(exc))
            return {
                "available": False,
                "battery_percent": None,
                "is_plugged_in": None,
                "seconds_left": None,
                "source": "UNAVAILABLE",
                "timestamp": now_iso,
            }


device_battery_service = DeviceBatteryService()
