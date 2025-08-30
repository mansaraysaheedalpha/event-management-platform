#app/main.py
from fastapi import FastAPI
from app.api.v1.api import api_router
from app.core.config import settings
from app.graphql.main import graphql_app


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
)


app.include_router(api_router, prefix="/api/v1")
app.mount("/graphql", graphql_app)


@app.get("/")
def read_root():
    return {"status": "Event Lifecycle Service is running"}
