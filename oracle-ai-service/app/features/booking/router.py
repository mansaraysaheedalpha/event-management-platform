# app/features/booking/router.py
from fastapi import APIRouter
from .schemas import BookingCallRequest, BookingCallResponse
from . import service

router = APIRouter()


@router.post(
    "/booking/call",
    response_model=BookingCallResponse,
    tags=["Booking"],
)
def book_call(request: BookingCallRequest):
    """
    Book a call with a speaker or expert.
    
    This endpoint allows users to schedule calls with speakers,
    providing a complete booking experience with confirmation details.
    """
    return service.book_speaker_call(request)
