from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import get_settings
from app.core.redis_client import RedisClient
from app.db.timescale import init_db
from app.collectors.signal_collector import EngagementSignalCollector
from app.middleware import (
    error_handler_middleware,
    app_error_handler,
    validation_error_handler,
    rate_limit_middleware,
    AppError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize global redis client with settings
import app.core.redis_client as redis_module
redis_module.redis_client = RedisClient(settings.REDIS_URL)

# Global signal collector instance
signal_collector: EngagementSignalCollector = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global signal_collector

    # Startup
    logger.info("🚀 Starting Engagement Conductor Agent Service...")

    try:
        # Connect to Redis
        await redis_module.redis_client.connect()

        # Initialize database
        await init_db()

        # Start signal collector
        signal_collector = EngagementSignalCollector(redis_module.redis_client)
        await signal_collector.start()

        logger.info("✅ Agent service ready")
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("👋 Shutting down Agent Service...")

    if signal_collector:
        await signal_collector.stop()

    await redis_module.redis_client.disconnect()


# Create FastAPI app
app = FastAPI(
    title="Engagement Conductor Agent",
    description="AI Agent for Real-Time Event Engagement Optimization",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware (production-safe)
cors_origins = settings.get_cors_origins() or [
    "http://localhost:3000",  # Development only
    "http://localhost:3001",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Add custom middleware (Phase 6)
app.middleware("http")(error_handler_middleware)
app.middleware("http")(rate_limit_middleware)

# Register exception handlers (Phase 6)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

# Include routers
from app.api.v1 import interventions, health, agent
app.include_router(health.router, tags=["Health"])
app.include_router(interventions.router, prefix="/api/v1", tags=["Interventions"])
app.include_router(agent.router, prefix="/api/v1", tags=["Agent"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Engagement Conductor Agent",
        "status": "operational",
        "version": "0.1.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    from app.collectors.session_tracker import session_tracker

    return {
        "status": "healthy",
        "redis": "connected" if redis_module.redis_client._client else "disconnected",
        "signal_collector": "running" if signal_collector and signal_collector.running else "stopped",
        "active_sessions": session_tracker.get_active_session_count()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
