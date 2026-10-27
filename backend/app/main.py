import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.db.session import engine
from app.db.init_db import init_db
import app.models  # Ensure models are imported for metadata registration
from app.api.v1 import api_v1_router
from app.api.v1.health import router as health_router

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("smart_battery_ai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure tables exist (helpful for local SQLite development)
    logger.info("Initializing database on startup...")
    init_db(engine)
    logger.info("Preloading ML models into memory...")
    try:
        from app.services.ml_service import ml_service
        ml_service.load_models()
        logger.info("ML models successfully preloaded and cached.")
    except Exception as exc:
        logger.warning("ML model preloading encountered an issue: %s", str(exc))
    logger.info("Startup complete. Service ready.")
    yield
    # Shutdown logic
    logger.info("Service shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Backend REST API for AI-Based Personalized Battery Charging Optimization",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler to prevent exposing raw stack traces
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please check system logs."},
    )


# Mount routes for /api and /api/v1 to provide both root-versioned and unversioned access
app.include_router(api_v1_router, prefix="/api")
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

# Root-level health check: GET /health
app.include_router(health_router, prefix="/health", tags=["Health"])


@app.get("/", summary="Root Index")
def root_index():
    return {
        "service": settings.APP_NAME,
        "docs_url": "/docs",
        "health_url": "/health",
        "api_prefix": "/api",
        "api_v1_prefix": settings.API_V1_PREFIX,
    }
