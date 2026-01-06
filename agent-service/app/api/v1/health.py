"""
Health Check Endpoints

Provides comprehensive health monitoring:
- Basic liveness check
- Readiness check (dependencies)
- Detailed health status
- Metrics endpoint
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, status, Response
from pydantic import BaseModel
import asyncio

# Database and Redis imports
from app.db.timescale import AsyncSessionLocal, engine
from sqlalchemy import text
from redis import asyncio as aioredis
from app.core.config import settings

# Import cost tracker for metrics
from app.middleware.rate_limiter import cost_tracker
from app.orchestrator.agent_manager import get_agent_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthStatus(BaseModel):
    """Health status response"""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    version: str = "1.0.0"
    uptime_seconds: Optional[float] = None


class DetailedHealthStatus(BaseModel):
    """Detailed health status with component checks"""
    status: str
    timestamp: str
    version: str = "1.0.0"
    components: Dict[str, Dict[str, Any]]
    uptime_seconds: Optional[float] = None


class MetricsResponse(BaseModel):
    """Metrics response"""
    timestamp: str
    agent_metrics: Dict[str, Any]
    cost_metrics: Dict[str, Any]
    system_metrics: Dict[str, Any]


# Track service start time
SERVICE_START_TIME = datetime.utcnow()


def get_uptime() -> float:
    """Get service uptime in seconds"""
    return (datetime.utcnow() - SERVICE_START_TIME).total_seconds()


async def check_database() -> Dict[str, Any]:
    """Check database connectivity and health"""
    try:
        async with AsyncSessionLocal() as session:
            # Simple query to check connection
            result = await session.execute(text("SELECT 1"))
            result.fetchone()

            return {
                "status": "healthy",
                "message": "Database connection successful",
                "response_time_ms": 0  # Could add timing
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
            "error": type(e).__name__
        }


async def check_redis() -> Dict[str, Any]:
    """Check Redis connectivity and health"""
    try:
        # Try to connect to Redis
        redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )

        # Ping Redis
        await redis.ping()
        await redis.close()

        return {
            "status": "healthy",
            "message": "Redis connection successful"
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Redis connection failed: {str(e)}",
            "error": type(e).__name__
        }


async def check_agent_orchestrator() -> Dict[str, Any]:
    """Check agent orchestrator health"""
    try:
        orchestrator = get_agent_orchestrator()
        stats = orchestrator.get_global_stats()

        return {
            "status": "healthy",
            "message": "Agent orchestrator operational",
            "active_sessions": stats["active_sessions"],
            "total_sessions": stats["total_sessions"],
            "total_interventions": stats["total_interventions"]
        }
    except Exception as e:
        logger.error(f"Agent orchestrator health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Agent orchestrator error: {str(e)}",
            "error": type(e).__name__
        }


@router.get("/health", response_model=HealthStatus, tags=["Health"])
async def health_check():
    """
    Basic health check endpoint (liveness probe).

    Returns 200 if service is running.
    """
    return HealthStatus(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        uptime_seconds=get_uptime()
    )


@router.get("/health/ready", response_model=HealthStatus, tags=["Health"])
async def readiness_check(response: Response):
    """
    Readiness check endpoint.

    Returns 200 if service is ready to accept requests (all dependencies healthy).
    Returns 503 if service is not ready.
    """
    # Check critical dependencies
    db_health = await check_database()
    redis_health = await check_redis()

    # Determine overall health
    if db_health["status"] == "healthy" and redis_health["status"] == "healthy":
        return HealthStatus(
            status="healthy",
            timestamp=datetime.utcnow().isoformat(),
            uptime_seconds=get_uptime()
        )
    else:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(
            status="unhealthy",
            timestamp=datetime.utcnow().isoformat(),
            uptime_seconds=get_uptime()
        )


@router.get("/health/detailed", response_model=DetailedHealthStatus, tags=["Health"])
async def detailed_health_check(response: Response):
    """
    Detailed health check with component status.

    Returns comprehensive health information for all service components.
    """
    # Check all components in parallel
    db_check, redis_check, agent_check = await asyncio.gather(
        check_database(),
        check_redis(),
        check_agent_orchestrator(),
        return_exceptions=True
    )

    # Handle exceptions
    if isinstance(db_check, Exception):
        db_check = {"status": "unhealthy", "message": str(db_check)}
    if isinstance(redis_check, Exception):
        redis_check = {"status": "unhealthy", "message": str(redis_check)}
    if isinstance(agent_check, Exception):
        agent_check = {"status": "unhealthy", "message": str(agent_check)}

    components = {
        "database": db_check,
        "redis": redis_check,
        "agent_orchestrator": agent_check
    }

    # Determine overall status
    statuses = [comp["status"] for comp in components.values()]
    if all(s == "healthy" for s in statuses):
        overall_status = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall_status = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        overall_status = "degraded"
        response.status_code = status.HTTP_200_OK

    return DetailedHealthStatus(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        components=components,
        uptime_seconds=get_uptime()
    )


@router.get("/metrics", response_model=MetricsResponse, tags=["Health"])
async def get_metrics():
    """
    Get service metrics.

    Returns operational metrics including agent performance and cost tracking.
    """
    # Get agent metrics
    orchestrator = get_agent_orchestrator()
    agent_stats = orchestrator.get_global_stats()

    # Get cost metrics
    cost_stats = cost_tracker.get_stats()

    # System metrics
    system_metrics = {
        "uptime_seconds": get_uptime(),
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

    return MetricsResponse(
        timestamp=datetime.utcnow().isoformat(),
        agent_metrics=agent_stats,
        cost_metrics=cost_stats,
        system_metrics=system_metrics
    )


@router.get("/health/ping", tags=["Health"])
async def ping():
    """
    Simple ping endpoint.

    Returns "pong" to verify service is responsive.
    """
    return {"status": "ok", "message": "pong", "timestamp": datetime.utcnow().isoformat()}
