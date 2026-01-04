# Backend Roadmap - Engagement Conductor Agent Service
## Detailed Implementation Guide

**Service Name:** `agent-service`
**Language:** Python 3.11+
**Framework:** FastAPI
**Database:** TimescaleDB (PostgreSQL), Redis

---

## 📁 Project Structure

```
agent-service/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI application entry
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                    # Configuration (env vars)
│   │   ├── llm_client.py                # Anthropic Claude client
│   │   └── redis_client.py              # Redis connection
│   ├── db/
│   │   ├── __init__.py
│   │   ├── timescale.py                 # TimescaleDB connection
│   │   └── models.py                    # SQLAlchemy models
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── signal_collector.py          # Real-time signal collection
│   │   └── session_tracker.py           # Per-session state tracking
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── anomaly_detector.py          # Anomaly detection
│   │   ├── intervention_selector.py     # Thompson Sampling selector
│   │   ├── content_generator.py         # LLM content generation
│   │   ├── engagement_conductor.py      # Main agent (LangGraph)
│   │   └── executors/
│   │       ├── __init__.py
│   │       ├── poll_executor.py         # Poll intervention
│   │       ├── chat_executor.py         # Chat prompt intervention
│   │       └── nudge_executor.py        # Nudge intervention
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   └── agent_manager.py             # Manages multiple sessions
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── interventions.py         # Intervention endpoints
│   │       ├── analytics.py             # Analytics endpoints
│   │       └── agent.py                 # Agent control endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   ├── anomaly.py                   # Anomaly dataclass
│   │   ├── intervention.py              # Intervention dataclass
│   │   └── engagement.py                # Engagement signals
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── engagement_score.py          # Score calculation
│   │   └── time_utils.py                # Time helpers
│   └── middleware/
│       ├── __init__.py
│       ├── error_handler.py             # Global error handling
│       └── rate_limiter.py              # Rate limiting
├── tests/
│   ├── __init__.py
│   ├── test_signal_collector.py
│   ├── test_anomaly_detector.py
│   └── test_intervention_selector.py
├── alembic/                             # Database migrations
│   ├── versions/
│   └── env.py
├── requirements.txt
├── .env.example
├── docker-compose.agent.yml
└── README.md
```

---

## Phase 0: Setup (Tasks 0.1 - 0.5)

### Task 0.1: Create Directory Structure ⬜

```bash
# Create agent-service directory
mkdir -p agent-service/app/{core,db,collectors,agents/executors,orchestrator,api/v1,models,utils,middleware}
mkdir -p agent-service/tests
mkdir -p agent-service/alembic/versions

# Create __init__.py files
touch agent-service/app/__init__.py
touch agent-service/app/core/__init__.py
touch agent-service/app/db/__init__.py
touch agent-service/app/collectors/__init__.py
touch agent-service/app/agents/__init__.py
touch agent-service/app/agents/executors/__init__.py
touch agent-service/app/orchestrator/__init__.py
touch agent-service/app/api/__init__.py
touch agent-service/app/api/v1/__init__.py
touch agent-service/app/models/__init__.py
touch agent-service/app/utils/__init__.py
touch agent-service/app/middleware/__init__.py
touch agent-service/tests/__init__.py
```

**Verification:** Directory structure exists

---

### Task 0.2: Python Environment & Dependencies ⬜

**File:** `agent-service/requirements.txt`

```txt
# Web Framework
fastapi==0.108.0
uvicorn[standard]==0.25.0
python-multipart==0.0.6

# Agent Framework
langgraph==0.2.0
langchain==0.3.0
langchain-anthropic==0.3.0
langsmith==0.3.0

# Async & WebSockets
aioredis==2.0.1
redis==5.0.1
websockets==12.0

# Database
sqlalchemy==2.0.23
asyncpg==0.29.0
psycopg2-binary==2.9.9
alembic==1.13.1

# Machine Learning
river==0.21.0
numpy==1.26.0
pandas==2.1.0
scikit-learn==1.3.0
scipy==1.11.4

# LLM Providers
anthropic==0.39.0
openai==1.54.0

# Utilities
pydantic==2.5.0
pydantic-settings==2.1.0
python-dotenv==1.0.0
httpx==0.25.2

# Monitoring
prometheus-client==0.19.0

# Development
pytest==7.4.3
pytest-asyncio==0.21.1
black==23.12.1
ruff==0.1.8
```

**Setup commands:**
```bash
cd agent-service
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Verification:** `pip list` shows all packages installed

---

### Task 0.3: Redis Connection ⬜

**File:** `agent-service/app/core/redis_client.py`

```python
import redis.asyncio as redis
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client for Pub/Sub and state management"""

    def __init__(self, url: str = "redis://localhost:6379"):
        self.url = url
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None

    async def connect(self):
        """Connect to Redis"""
        try:
            self._client = await redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._client.ping()
            logger.info("✅ Connected to Redis")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Disconnect from Redis"""
        if self._client:
            await self._client.close()
            logger.info("Disconnected from Redis")

    @property
    def client(self) -> redis.Redis:
        """Get Redis client"""
        if not self._client:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._client

    async def subscribe(self, *channels: str):
        """Subscribe to channels"""
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(*channels)
        return self._pubsub

    async def publish(self, channel: str, message: str):
        """Publish message to channel"""
        await self._client.publish(channel, message)


# Global instance
redis_client = RedisClient()
```

**File:** `agent-service/app/core/config.py`

```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # TimescaleDB
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/events"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # LangSmith (optional)
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_PROJECT: str = "engagement-conductor"

    # Agent Settings
    ENGAGEMENT_THRESHOLD: float = 0.6
    ANOMALY_WARNING_THRESHOLD: float = 0.6
    ANOMALY_CRITICAL_THRESHOLD: float = 0.8

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

**File:** `agent-service/.env.example`

```env
# Redis
REDIS_URL=redis://localhost:6379

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/events

# Anthropic
ANTHROPIC_API_KEY=your-api-key-here

# LangSmith (optional)
LANGCHAIN_API_KEY=
LANGCHAIN_TRACING_V2=false
LANGCHAIN_PROJECT=engagement-conductor

# Agent
ENGAGEMENT_THRESHOLD=0.6
ANOMALY_WARNING_THRESHOLD=0.6
ANOMALY_CRITICAL_THRESHOLD=0.8
```

**Verification:** Can connect to Redis successfully

---

### Task 0.4: TimescaleDB Docker Setup ⬜

**File:** `agent-service/docker-compose.agent.yml`

```yaml
version: '3.8'

services:
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    container_name: timescaledb_agent
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: events
    ports:
      - "5432:5432"
    volumes:
      - timescale_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  timescale_data:
```

**Start command:**
```bash
docker-compose -f docker-compose.agent.yml up -d
```

**Verification:** `docker ps` shows timescaledb running

---

### Task 0.5: Database Schema ⬜

**File:** `agent-service/app/db/timescale.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

# Convert psycopg2 URL to asyncpg
DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()


async def init_db():
    """Initialize database and create tables"""
    async with engine.begin() as conn:
        # Enable TimescaleDB extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

        # Create tables
        await conn.run_sync(Base.metadata.create_all)

        # Convert to hypertables
        try:
            await conn.execute(
                "SELECT create_hypertable('engagement_metrics', 'time', if_not_exists => TRUE);"
            )
            await conn.execute(
                "SELECT create_hypertable('interventions', 'timestamp', if_not_exists => TRUE);"
            )
            await conn.execute(
                "SELECT create_hypertable('agent_performance', 'time', if_not_exists => TRUE);"
            )
            logger.info("✅ TimescaleDB hypertables created")
        except Exception as e:
            logger.warning(f"Hypertables may already exist: {e}")


async def get_db():
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        yield session
```

**File:** `agent-service/app/db/models.py`

```python
from sqlalchemy import Column, String, Float, Integer, Boolean, JSON, TIMESTAMP, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from app.db.timescale import Base


class EngagementMetric(Base):
    __tablename__ = "engagement_metrics"

    time = Column(TIMESTAMP, primary_key=True, default=datetime.utcnow)
    session_id = Column(UUID(as_uuid=True), primary_key=True)
    event_id = Column(UUID(as_uuid=True), nullable=False)
    engagement_score = Column(Float, nullable=False)
    chat_msgs_per_min = Column(Float)
    poll_participation = Column(Float)
    active_users = Column(Integer)
    reactions_per_min = Column(Float)
    user_leave_rate = Column(Float)
    metadata = Column(JSON)

    __table_args__ = (
        Index('idx_session_time', 'session_id', 'time'),
        Index('idx_engagement_score', 'engagement_score'),
    )


class Intervention(Base):
    __tablename__ = "interventions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    type = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(String, nullable=True)
    outcome = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)

    __table_args__ = (
        Index('idx_intervention_session', 'session_id', 'timestamp'),
    )


class AgentPerformance(Base):
    __tablename__ = "agent_performance"

    time = Column(TIMESTAMP, primary_key=True, default=datetime.utcnow)
    agent_id = Column(String(100), primary_key=True)
    intervention_type = Column(String(50), nullable=False)
    success = Column(Boolean, nullable=False)
    engagement_delta = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    metadata = Column(JSON, nullable=True)

    __table_args__ = (
        Index('idx_agent_performance', 'agent_id', 'time'),
    )
```

**File:** `agent-service/app/main.py` (Initial version)

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from app.core.config import get_settings
from app.core.redis_client import redis_client
from app.db.timescale import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("🚀 Starting Engagement Conductor Agent Service...")

    # Connect to Redis
    await redis_client.connect()

    # Initialize database
    await init_db()

    logger.info("✅ Agent service ready")

    yield

    # Shutdown
    logger.info("👋 Shutting down Agent Service...")
    await redis_client.disconnect()


app = FastAPI(
    title="Engagement Conductor Agent",
    description="AI Agent for Real-Time Event Engagement Optimization",
    version="0.1.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {
        "service": "Engagement Conductor Agent",
        "status": "operational",
        "version": "0.1.0"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

**Start command:**
```bash
cd agent-service
python -m uvicorn app.main:app --reload --port 8001
```

**Verification:**
- Service starts without errors
- Visit http://localhost:8001/docs (FastAPI docs)
- Health check returns 200

---

## Phase 1: Signal Collection (Tasks 1.1 - 1.6)

### Task 1.1: EngagementSignalCollector ⬜

**File:** `agent-service/app/collectors/signal_collector.py`

```python
import asyncio
import redis.asyncio as redis
import json
from typing import Dict
from datetime import datetime
import logging

from app.core.redis_client import redis_client
from app.collectors.session_tracker import SessionTracker
from app.db.timescale import AsyncSessionLocal
from app.db.models import EngagementMetric

logger = logging.getLogger(__name__)


class EngagementSignalCollector:
    """Collects real-time engagement signals from WebSocket gateways"""

    def __init__(self):
        self.active_sessions: Dict[str, SessionTracker] = {}
        self.running = False

    async def start(self):
        """Start collecting signals"""
        self.running = True
        logger.info("🎧 Starting signal collection...")

        await asyncio.gather(
            self.listen_chat_events(),
            self.listen_presence_events(),
            self.listen_poll_events(),
            self.listen_reaction_events(),
            self.compute_engagement_scores()
        )

    async def stop(self):
        """Stop collecting signals"""
        self.running = False
        logger.info("Stopping signal collection...")

    async def listen_chat_events(self):
        """Subscribe to chat messages"""
        pubsub = await redis_client.subscribe('chat:message:new')

        logger.info("✅ Subscribed to chat:message:new")

        async for message in pubsub.listen():
            if not self.running:
                break

            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    await self.process_chat_event(data)
                except Exception as e:
                    logger.error(f"Error processing chat event: {e}")

    async def process_chat_event(self, data: dict):
        """Process a chat message event"""
        session_id = data.get('sessionId')
        if not session_id:
            return

        # Get or create session tracker
        tracker = self.get_or_create_tracker(session_id, data.get('eventId'))
        tracker.record_chat_message(data)

        # Publish signal
        await self.publish_signal(session_id, {
            'type': 'chat',
            'timestamp': datetime.now().isoformat(),
            'value': tracker.get_chat_rate()
        })

    # Continue in next comment...
```

**Note:** This is just the start. Task 1.1 continues with other methods. Let me know when you're ready for the rest.

---

### Task 1.2 - 1.6: [Will be detailed when we start Phase 1]

---

## Phase 2: Anomaly Detection (Tasks 2.1 - 2.5)

### Task 2.1 - 2.5: [Will be detailed when we start Phase 2]

---

## Phase 3: Basic Intervention (Tasks 3.1 - 3.7)

### Task 3.1 - 3.7: [Will be detailed when we start Phase 3]

---

## Phase 4: LLM Integration (Tasks 4.1 - 4.4)

### Task 4.1 - 4.4: [Will be detailed when we start Phase 4]

---

## Phase 5: Full Agent Loop (Tasks 5.1 - 5.6)

### Task 5.1 - 5.6: [Will be detailed when we start Phase 5]

---

## Phase 6: Polish & Testing (Tasks 6.1 - 6.3)

### Task 6.1 - 6.3: [Will be detailed when we start Phase 6]

---

## Testing Strategy

For each phase, we'll test:

1. **Unit Tests**: Individual functions/classes
2. **Integration Tests**: Components working together
3. **Manual Tests**: Real-world scenarios with actual data

**Example test structure:**
```python
# tests/test_signal_collector.py
import pytest
from app.collectors.signal_collector import EngagementSignalCollector

@pytest.mark.asyncio
async def test_chat_event_processing():
    collector = EngagementSignalCollector()
    event = {
        'sessionId': 'test-session-123',
        'eventId': 'test-event-456',
        'userId': 'user-789',
        'content': 'Test message'
    }
    await collector.process_chat_event(event)
    # Assert tracker was updated
```

---

## Deployment Checklist

Before deploying to production:

- [ ] All tests passing
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Redis connection verified
- [ ] TimescaleDB hypertables created
- [ ] API documentation updated
- [ ] Logging configured
- [ ] Error handling tested
- [ ] Rate limiting enabled
- [ ] Health checks working

---

**Next Steps:** Complete Phase 0 tasks, then move to Phase 1.
