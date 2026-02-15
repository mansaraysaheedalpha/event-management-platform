from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import text
from app.core.config import get_settings
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import ssl
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

# Convert psycopg2 URL to asyncpg and handle sslmode parameter
# asyncpg doesn't accept sslmode as URL param, needs ssl context instead
def prepare_asyncpg_url(url: str) -> tuple[str, dict]:
    """Convert DATABASE_URL to asyncpg format and extract SSL settings."""
    # Replace driver
    url = url.replace("postgresql://", "postgresql+asyncpg://")

    # Parse URL to extract sslmode
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    connect_args = {}

    # Handle sslmode parameter
    if "sslmode" in query_params:
        sslmode = query_params.pop("sslmode")[0]
        if sslmode in ("require", "verify-ca", "verify-full"):
            # Create SSL context for secure connection
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ssl_context

    # Rebuild URL without sslmode
    new_query = urlencode({k: v[0] for k, v in query_params.items()})
    new_parsed = parsed._replace(query=new_query)
    clean_url = urlunparse(new_parsed)

    return clean_url, connect_args

# Database is optional - service can run without it using Redis for state
engine = None
AsyncSessionLocal = None

if settings.DATABASE_URL:
    DATABASE_URL, connect_args = prepare_asyncpg_url(settings.DATABASE_URL)
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True, connect_args=connect_args)
    # Create async session factory
    AsyncSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
else:
    logger.warning("DATABASE_URL not configured. Database features will be disabled.")

# Base class for models
Base = declarative_base()


async def init_db():
    """Initialize database and create tables"""
    if engine is None:
        logger.warning("Database engine not initialized. Skipping database setup.")
        return

    # Import models to register them with Base.metadata
    from app.db import models  # noqa: F401
    from app.models import anomaly  # noqa: F401

    async with engine.begin() as conn:
        # Enable TimescaleDB extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))

        # Create tables
        await conn.run_sync(Base.metadata.create_all)

        # Convert to hypertables (time-series optimization)
        # Note: Only tables with composite primary keys including time can be hypertables
        # Tables with UUID primary keys (interventions, anomalies) remain regular tables
        hypertable_configs = [
            # (table_name, time_column) - only tables where time is part of PK
            ("engagement_metrics", "time"),
            ("agent_performance", "time"),
        ]

        for table_name, time_column in hypertable_configs:
            try:
                await conn.execute(
                    text(f"SELECT create_hypertable('{table_name}', '{time_column}', if_not_exists => TRUE);")
                )
                logger.info(f"✅ Hypertable created: {table_name}")
            except Exception as e:
                # Table may already be a hypertable, or TimescaleDB not available
                logger.debug(f"Hypertable {table_name}: {e}")

        logger.info("TimescaleDB hypertable setup complete")


async def verify_database_connection() -> bool:
    """
    MED-14 FIX: Verify database connection is available at startup.

    Call this during application startup to fail fast with a clear error
    instead of silently running in degraded mode.

    Returns:
        True if DB is available, False if running in Redis-only mode
    """
    if AsyncSessionLocal is None:
        logger.warning(
            "DATABASE_URL not configured. Agent service will run in "
            "Redis-only mode (no persistence for metrics, interventions, or anomalies)."
        )
        return False

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            logger.info("Database connection verified successfully")
            return True
    except Exception as e:
        logger.error(
            f"Database connection FAILED: {e}. "
            f"Service will run in Redis-only mode. "
            f"Fix DATABASE_URL or check database availability."
        )
        return False


async def get_db():
    """Dependency for getting database session"""
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not configured. Set DATABASE_URL environment variable.")
    async with AsyncSessionLocal() as session:
        yield session
