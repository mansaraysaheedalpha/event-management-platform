# app/main.py
from fastapi import FastAPI
from app.core.config import settings
from app.core.limiter import limiter  # Import from separate module to avoid circular imports
from contextlib import asynccontextmanager
from app.db.base_class import Base
from app.db.session import engine
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded


# ✅ THE FINAL FIX: The Lifespan Event Handler
# This function will run once when the application starts up.
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application starting up...")
    Base.metadata.create_all(bind=engine)
    print("Database tables checked and created if necessary.")

    # Initialize background scheduler for waitlist tasks
    from app.scheduler import init_scheduler
    init_scheduler()
    print("Background scheduler initialized and started.")

    yield

    print("Application shutting down...")

    # Shutdown scheduler first — stop producing new work before closing Kafka
    from app.scheduler import shutdown_scheduler
    shutdown_scheduler()
    print("Background scheduler shut down.")

    # Shutdown Kafka producer — flush remaining messages then close
    from app.core.kafka_producer import shutdown_kafka_producer
    shutdown_kafka_producer()
    print("Kafka producer shut down.")


app = FastAPI(
    title="Event Dynamics Event-Lifecycle Microservice",
    version="1.0.0",
    description="""
        🚀 **Event Dynamics Event Management Service**

        The core orchestrator for intelligent event management.

        ## Features

        * **Event Management**: Create, update, and manage events
        * **Session Scheduling**: Organize sessions within events
        * **Speaker Management**: Maintain speaker profiles and assignments
        * **Venue Management**: Handle venue information and assignments
        * **Registration System**: Manage attendee registrations
        * **Presentation Upload**: Handle presentation files and processing
        * **Multi-tenant**: Organization-scoped data isolation
        * **Real-time Integration**: Internal notifications for live updates

        ## Authentication

        Most endpoints require JWT authentication via the `Authorization: Bearer <token>` header.

        ## Public Endpoints

        Some endpoints under `/public/` are accessible without authentication for event discovery.
        """,
    lifespan=lifespan,
)

# Rate limiter configuration (imported from app.core.limiter)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Parse CORS origins from environment (comma-separated)
origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allow origins from environment
    allow_credentials=True,  # Allow cookies and authorization headers
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Import routers after app is created to avoid circular imports
from app.api.v1.api import api_router
from app.graphql.router import graphql_router

app.include_router(api_router, prefix="/api/v1")
app.include_router(graphql_router, prefix="/graphql")


@app.get("/")
def read_root():
    return {"status": "Event Lifecycle Service is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
