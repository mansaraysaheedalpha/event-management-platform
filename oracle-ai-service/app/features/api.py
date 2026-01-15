# app/features/api.py
from fastapi import APIRouter
from app.features import (
    analytics,
    networking,
    analysis,
    recommendations,
    optimization,
    predictions,
    assistant,
    reporting,
    management,
    testing,
    intelligence,
    enrichment,
    networking_analytics,
)

api_router = APIRouter()

api_router.include_router(analytics.router)
api_router.include_router(networking.router)
api_router.include_router(analysis.router)
api_router.include_router(recommendations.router)
api_router.include_router(optimization.router)
api_router.include_router(predictions.router)
api_router.include_router(assistant.router)
api_router.include_router(reporting.router)
api_router.include_router(management.router)
api_router.include_router(testing.router)
api_router.include_router(intelligence.router)

# Sprint 2: Profile Enrichment
api_router.include_router(enrichment.router)

# Sprint 9: Organizer Networking Analytics
api_router.include_router(networking_analytics.router)
