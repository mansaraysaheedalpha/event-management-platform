# app/features/assistant/router.py
from fastapi import APIRouter
from .schemas import *
from . import service

router = APIRouter()


@router.post(
    "/assistant/concierge", response_model=ConciergeResponse, tags=["AI Assistant"]
)
def get_concierge_answer(request: ConciergeRequest):
    """
    Provides an AI-powered response to an attendee's or speaker's query.
    """
    return service.get_concierge_response(request)


@router.post(
    "/assistant/smart-notifications",
    response_model=SmartNotificationResponse,
    tags=["AI Assistant"],
)
def get_smart_notification_schedule(request: SmartNotificationRequest):
    """Calculates the optimal alert scheduling based on user behavior."""
    return service.get_smart_notification_timing(request)
