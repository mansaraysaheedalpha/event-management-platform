# app/main.py
from fastapi import FastAPI
from app.api.v1.api import api_router
from app.core.config import settings
from contextlib import asynccontextmanager
from app.db.base_class import Base
from app.db.session import engine
from app.graphql.router import graphql_router
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
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

    # Shutdown background scheduler
    from app.scheduler import shutdown_scheduler
    shutdown_scheduler()
    print("Background scheduler shut down.")


app = FastAPI(
    title="GlobalConnect Event-Lifecycle Microservice",
    version="1.0.0",
    description="""
        🚀 **GlobalConnect Event Management Service**

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

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)
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

app.include_router(api_router, prefix="/api/v1")
app.include_router(graphql_router, prefix="/graphql")


@app.get("/")
def read_root():
    return {"status": "Event Lifecycle Service is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
