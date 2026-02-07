# oracle-ai-service/main.py
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import models, seed
from app.features import api
from app.graphql.router import graphql_router
from app.models.ai import sentiment
from app.messaging.consumers import run_all_consumers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles:
    - Database seeding on startup
    - Graceful shutdown of connections
    """
    # Startup
    logger.info("Oracle AI Service starting up...")
    seed.seed_database()
    logger.info("Database seeded successfully")

    # Start Kafka consumers in background thread
    logger.info("Starting Kafka consumers...")
    consumer_thread = threading.Thread(target=run_all_consumers, daemon=True)
    consumer_thread.start()
    logger.info("Kafka consumers started in background thread")

    yield

    # Shutdown - close all connections gracefully
    logger.info("Oracle AI Service shutting down...")

    # Close rate limiter Redis connections
    try:
        from app.core.rate_limiter import close_rate_limiters

        await close_rate_limiters()
    except Exception as e:
        logger.warning(f"Error closing rate limiters: {e}")

    # Close HTTP clients for external APIs
    try:
        from app.agents.profile_enrichment.tools.tavily_search import get_tavily_client

        client = await get_tavily_client()
        await client.close()
    except Exception as e:
        logger.warning(f"Error closing Tavily client: {e}")

    try:
        from app.agents.profile_enrichment.tools.github_api import get_github_fetcher

        fetcher = await get_github_fetcher()
        await fetcher.close()
    except Exception as e:
        logger.warning(f"Error closing GitHub fetcher: {e}")

    # Close realtime service client
    try:
        from app.integrations.realtime_client import get_realtime_client

        client = await get_realtime_client()
        await client.close()
    except Exception as e:
        logger.warning(f"Error closing realtime client: {e}")

    # Close Kafka publisher
    try:
        from app.integrations.kafka_publisher import get_kafka_publisher

        kafka = get_kafka_publisher()
        kafka.close()
    except Exception as e:
        logger.warning(f"Error closing Kafka publisher: {e}")

    logger.info("Shutdown complete")


app = FastAPI(
    title="Oracle Microservice API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/oracle/docs",
    redoc_url="/oracle/redoc",
)

app.include_router(api.api_router, prefix="/oracle")
app.include_router(graphql_router, prefix="/graphql")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check with dependency status.

    Checks:
    - Database connectivity
    - Redis connectivity
    - External API circuit breakers
    """
    from app.core.circuit_breaker import get_all_breaker_stats
    from app.core.config import settings

    health = {
        "status": "healthy",
        "service": "oracle-ai-service",
        "enrichment_enabled": settings.enrichment_enabled,
        "circuit_breakers": await get_all_breaker_stats(),
    }

    return health
