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
    connect_webhooks,
    organizations,
    waitlist,
    admin_waitlist,
    analytics,
    reports,
    ab_testing,
    sponsors,
    sponsor_campaigns,
    sponsor_user_permissions,
    sponsor_team,
    sponsor_user_settings,
    calendar,
    email_preferences,
    demo_requests,
    check_in,
    sms_webhook,
    venue_directory,
    venue_spaces,
    venue_photos,
    venue_amenities,
    venue_verification,
    venue_admin,
    rfps,
    venue_rfps,
    exchange_rates,
    rfp_notifications,
    venue_waitlist,
    venue_availability,
    health,
)

# This is the main router for the v1 API.
# It will include all the specific endpoint routers.
api_router = APIRouter()

# Health checks
api_router.include_router(health.router)

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
api_router.include_router(connect_webhooks.router, prefix="/webhooks", tags=["connect-webhooks"])
api_router.include_router(offer_webhooks.router, prefix="/offer-webhooks", tags=["offer-webhooks"])
api_router.include_router(organizations.router)
api_router.include_router(sponsors.router, prefix="/sponsors", tags=["Sponsors"])
api_router.include_router(sponsor_campaigns.router, prefix="/sponsors-campaigns", tags=["Sponsor Campaigns"])
api_router.include_router(sponsor_user_permissions.router, prefix="/sponsor-users", tags=["Sponsor User Permissions"])
api_router.include_router(sponsor_team.router, prefix="/sponsor-team", tags=["Sponsor Team Management"])
api_router.include_router(sponsor_user_settings.router, prefix="/sponsor-settings", tags=["Sponsor User Settings"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["Calendar"])
api_router.include_router(email_preferences.router, prefix="/email-preferences", tags=["Email Preferences"])
api_router.include_router(demo_requests.router, tags=["Demo Requests"])
api_router.include_router(check_in.router, tags=["Check-in"])
api_router.include_router(sms_webhook.router, prefix="/webhooks/sms", tags=["SMS Webhook"])

# Venue Sourcing — Golden Directory
api_router.include_router(venue_directory.router, tags=["Venue Directory"])
api_router.include_router(venue_spaces.router, tags=["Venue Spaces"])
api_router.include_router(venue_photos.router, tags=["Venue Photos"])
api_router.include_router(venue_amenities.router, tags=["Venue Amenities"])
api_router.include_router(venue_verification.router, tags=["Venue Verification"])
api_router.include_router(venue_admin.router, tags=["Venue Admin"])

# Venue Sourcing — RFP System
api_router.include_router(rfps.router, tags=["RFPs"])
api_router.include_router(venue_rfps.router, tags=["Venue RFPs"])
api_router.include_router(exchange_rates.router, tags=["Exchange Rates"])
api_router.include_router(rfp_notifications.router, tags=["RFP Notifications"])

# Venue Sourcing — Waitlist System
api_router.include_router(venue_waitlist.router, tags=["Venue Waitlist"])
api_router.include_router(venue_availability.router, tags=["Venue Availability"])

