# app/api/v1/api.py

from fastapi import APIRouter
from app.api.v1.endpoints import (
    public,
    events,
    sessions,
    speakers,
    registrations,
    venues,
    presentations,
    blueprints,
    internals,
    ads,
    offers
)

# This is the main router for the v1 API.
# It will include all the specific endpoint routers.
api_router = APIRouter()

api_router.include_router(public.router)
api_router.include_router(events.router)
api_router.include_router(sessions.router)
api_router.include_router(speakers.router)
api_router.include_router(registrations.router)
api_router.include_router(venues.router)
api_router.include_router(presentations.router)
api_router.include_router(blueprints.router)
api_router.include_router(internals.router)
api_router.include_router(ads.router)
api_router.include_router(offers.router)

