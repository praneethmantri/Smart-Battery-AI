from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.users import router as users_router
from app.api.v1.charging_sessions import router as charging_sessions_router
from app.api.v1.charging import router as charging_router
from app.api.v1.battery_readings import router as battery_readings_router
from app.api.v1.predictions import router as predictions_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.device_battery import router as device_battery_router
from app.api.v1.telemetry import router as telemetry_router

api_v1_router = APIRouter()

# Register modular sub-routers
api_v1_router.include_router(health_router, prefix="/health", tags=["Health"])
api_v1_router.include_router(users_router, prefix="/users", tags=["Users"])
api_v1_router.include_router(charging_sessions_router, prefix="/charging-sessions", tags=["Charging Sessions"])
api_v1_router.include_router(charging_router, prefix="/charging", tags=["Charging (Legacy / Direct)"])
api_v1_router.include_router(battery_readings_router, prefix="/battery-readings", tags=["Battery Readings"])
api_v1_router.include_router(predictions_router, prefix="/predictions", tags=["Predictions"])
api_v1_router.include_router(predictions_router, prefix="/predict", tags=["Predictions"])
api_v1_router.include_router(recommendations_router, prefix="/recommendations", tags=["Recommendations"])
api_v1_router.include_router(device_battery_router, prefix="/device-battery", tags=["Device Battery"])
api_v1_router.include_router(telemetry_router, prefix="/telemetry", tags=["Windows Telemetry"])

__all__ = ["api_v1_router"]
