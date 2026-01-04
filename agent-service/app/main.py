from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from app.core.config import get_settings
from app.core.redis_client import redis_client, RedisClient
from app.db.timescale import init_db
from app.collectors.signal_collector import EngagementSignalCollector

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
        await redis_client.connect()

        # Initialize database
        await init_db()

        # Start signal collector
        signal_collector = EngagementSignalCollector(redis_client)
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

    await redis_client.disconnect()


# Create FastAPI app
app = FastAPI(
    title="Engagement Conductor Agent",
    description="AI Agent for Real-Time Event Engagement Optimization",
    version="0.1.0",
    lifespan=lifespan
)

# Include routers
from app.api.v1 import interventions
app.include_router(interventions.router, prefix="/api/v1")


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
        "redis": "connected" if redis_client._client else "disconnected",
        "signal_collector": "running" if signal_collector and signal_collector.running else "stopped",
        "active_sessions": session_tracker.get_active_session_count()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
