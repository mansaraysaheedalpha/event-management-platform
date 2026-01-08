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

DATABASE_URL, connect_args = prepare_asyncpg_url(settings.DATABASE_URL)

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True, connect_args=connect_args)

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
