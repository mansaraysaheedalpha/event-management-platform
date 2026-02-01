"""
Admin API Endpoints
For database management and system administration

SECURITY: These endpoints should be protected in production
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
import logging

from app.db.timescale import engine, Base

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/db/create-tables")
async def create_tables():
    """
    Manually create all database tables.

    WARNING: This should be protected in production!
    """
    if engine is None:
        raise HTTPException(
            status_code=500,
            detail="Database not configured. Set DATABASE_URL environment variable."
        )

    try:
        # Import models to register them with Base.metadata
        from app.db import models  # noqa: F401
        from app.models import anomaly  # noqa: F401

        async with engine.begin() as conn:
            # Enable TimescaleDB extension
            logger.info("Enabling TimescaleDB extension...")
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))

            # Create all tables
            logger.info("Creating tables...")
            await conn.run_sync(Base.metadata.create_all)

            # Convert to hypertables
            logger.info("Converting to hypertables...")
            try:
                await conn.execute(
                    text("SELECT create_hypertable('engagement_metrics', 'time', if_not_exists => TRUE);")
                )
                await conn.execute(
                    text("SELECT create_hypertable('interventions', 'timestamp', if_not_exists => TRUE);")
                )
                await conn.execute(
                    text("SELECT create_hypertable('agent_performance', 'time', if_not_exists => TRUE);")
                )
                await conn.execute(
                    text("SELECT create_hypertable('anomalies', 'timestamp', if_not_exists => TRUE);")
                )
                logger.info("✅ Hypertables created successfully")
            except Exception as e:
                logger.warning(f"Hypertables may already exist: {e}")

        return {
            "status": "success",
            "message": "Database tables created successfully",
            "tables": [
                "engagement_metrics",
                "interventions",
                "agent_performance",
                "anomalies"
            ]
        }

    except Exception as e:
        logger.error(f"Failed to create tables: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create tables: {str(e)}"
        )


@router.get("/db/list-tables")
async def list_tables():
    """List all tables in the database"""
    if engine is None:
        raise HTTPException(
            status_code=500,
            detail="Database not configured"
        )

    try:
        async with engine.begin() as conn:
            result = await conn.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
            ))
            tables = [row[0] for row in result.fetchall()]

        return {
            "tables": tables,
            "count": len(tables)
        }

    except Exception as e:
        logger.error(f"Failed to list tables: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list tables: {str(e)}"
        )
