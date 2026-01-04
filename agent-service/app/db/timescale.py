from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import text
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

# Convert psycopg2 URL to asyncpg (PostgreSQL async driver)
DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Base class for models
Base = declarative_base()


async def init_db():
    """Initialize database and create tables"""
    # Import models to register them with Base.metadata
    from app.db import models  # noqa: F401
    from app.models import anomaly  # noqa: F401

    async with engine.begin() as conn:
        # Enable TimescaleDB extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))

        # Create tables
        await conn.run_sync(Base.metadata.create_all)

        # Convert to hypertables (time-series optimization)
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
            logger.info("✅ TimescaleDB hypertables created")
        except Exception as e:
            logger.warning(f"Hypertables may already exist: {e}")


async def get_db():
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        yield session
