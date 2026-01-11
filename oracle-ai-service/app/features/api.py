# app/features/api.py
from fastapi import APIRouter
from app.features import  (
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
    booking,
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
api_router.include_router(booking.router)
