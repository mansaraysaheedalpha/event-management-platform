# app/main.py
"""
Main FastAPI application entry point.
This is where we create and configure the FastAPI app instance.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings


def create_application() -> FastAPI:
    """
    Application factory pattern.
    Creates and configures the FastAPI application instance.

    Why use a factory function?
    - Easier testing (we can create multiple app instances)
    - Better configuration management
    - Cleaner separation of concerns
    """

    # Create FastAPI instance
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
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
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
    )

    # Add CORS middleware
    # This allows your frontend (React app, mobile app, etc.) to access the API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",  # React development server
            "http://localhost:8080",  # Vue development server
            "https://globalconnect.com",  # Your production frontend
        ],
        allow_credentials=True,
        allow_methods=["*"],  # Allow all HTTP methods
        allow_headers=["*"],  # Allow all headers
    )

    return app


# Create the FastAPI app instance
app = create_application()


# Root endpoint - Health check
@app.get("/")
async def root():
    """
    Root endpoint for health checking and basic API information.

    Returns:
        dict: Basic API information and health status
    """
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.version,
        "environment": settings.environment,
        "status": "healthy",
        "docs_url": f"{settings.api_v1_prefix}/docs",
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Detailed health check endpoint.
    Used by load balancers and monitoring systems.

    Returns:
        dict: Detailed health information
    """
    return {
        "status": "healthy",
        "service": "event-management",
        "version": settings.version,
        "environment": settings.environment,
    }


# Add API version info
@app.get(f"{settings.api_v1_prefix}/info")
async def api_info():
    """
    API version and configuration information.
    Useful for debugging and monitoring.
    """
    return {
        "api_version": "v1",
        "service": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "features": [
            "Event Management",
            "Session Scheduling",
            "Speaker Management",
            "Venue Management",
            "Registration System",
            "Presentation Upload",
            "Multi-tenant Support",
            "Real-time Integration",
        ],
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """
    Runs when the application starts up.
    Perfect place for:
    - Database connections
    - Cache initialization
    - Background task setup
    """
    print(f"🚀 Starting {settings.app_name} v{settings.version}")
    print(f"📍 Environment: {settings.environment}")
    print(f"📚 API Documentation: http://localhost:8000{settings.api_v1_prefix}/docs")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """
    Runs when the application shuts down.
    Perfect place for:
    - Closing database connections
    - Cleanup tasks
    - Graceful shutdown
    """
    print(f"👋 Shutting down {settings.app_name}")


# If running directly (for development)
if __name__ == "__main__":
    import uvicorn

    # Run the server
    uvicorn.run(
        "app.main:app",  # Path to the FastAPI app
        host="0.0.0.0",  # Listen on all interfaces
        port=8000,  # Port number
        reload=True,  # Auto-reload on code changes (development only)
        log_level="info",  # Logging level
    )
