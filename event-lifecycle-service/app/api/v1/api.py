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
    offers,
    webhooks,
    offer_webhooks,
    organizations,
    waitlist,
    admin_waitlist,
    analytics,
    reports,
    ab_testing,
    sponsors,
    sponsor_campaigns,
    sponsor_user_permissions,
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
api_router.include_router(ads.router, prefix="/ads", tags=["Ads"])
api_router.include_router(offers.router, prefix="/offers", tags=["offers"])
api_router.include_router(waitlist.router, tags=["Waitlist"])
api_router.include_router(admin_waitlist.router, prefix="/admin", tags=["Admin - Waitlist"])
api_router.include_router(analytics.router, tags=["Analytics"])
api_router.include_router(reports.router, tags=["Reports"])
api_router.include_router(ab_testing.router, tags=["A/B Testing"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(offer_webhooks.router, prefix="/offer-webhooks", tags=["offer-webhooks"])
api_router.include_router(organizations.router)
api_router.include_router(sponsors.router, prefix="/sponsors", tags=["Sponsors"])
api_router.include_router(sponsor_campaigns.router, prefix="/sponsors-campaigns", tags=["Sponsor Campaigns"])
api_router.include_router(sponsor_user_permissions.router, prefix="/sponsor-users", tags=["Sponsor User Permissions"])

