# app/graphql/venue_waitlist_queries.py
"""GraphQL Venue Waitlist queries — called from the main Query class."""
from typing import Optional
from datetime import datetime, timezone
from strawberry.types import Info
from fastapi import HTTPException

from ..crud import crud_venue_waitlist, crud_venue_availability
from ..models.venue_photo import VenuePhoto
from ..models.venue import Venue
from ..models.venue_waitlist_entry import VenueWaitlistEntry
from .venue_waitlist_types import (
    VenueWaitlistEntryType,
    WaitlistEntryListResult,
    VenueAvailabilityType,
    AvailabilityBadge,
    AvailabilitySignalSummary,
    ExistingWaitlistCheck,
)


def _get_user_org(info: Info) -> tuple:
    """Extract user and org_id from context."""
    user = info.context.user
    if not user or not user.get("orgId"):
        raise HTTPException(status_code=403, detail="Not authorized")
    return user, user["orgId"]


def _entry_to_gql(db, entry) -> VenueWaitlistEntryType:
    """Convert a VenueWaitlistEntry model to GQL type."""
    # Get venue cover photo
    cover_photo_url = None
    if entry.venue:
        cover = (
            db.query(VenuePhoto.url)
            .filter(
                VenuePhoto.venue_id == entry.venue.id, VenuePhoto.is_cover == True
            )
            .first()
        )
        if cover:
            cover_photo_url = cover.url

    # Calculate queue position
    queue_position = crud_venue_waitlist.get_queue_position(db, entry=entry)

    # Calculate hold_remaining_seconds if offered
    hold_remaining_seconds = None
    if entry.status == "offered" and entry.hold_expires_at:
        now = datetime.now(timezone.utc)
        if entry.hold_expires_at > now:
            delta = entry.hold_expires_at - now
            hold_remaining_seconds = int(delta.total_seconds())

    return VenueWaitlistEntryType(
        id=entry.id,
        organizationId=entry.organization_id,
        venueId=entry.venue_id,
        venueName=entry.venue.name if entry.venue else "Unknown",
        venueSlug=entry.venue.slug if entry.venue else None,
        venueCoverPhotoUrl=cover_photo_url,
        venueCity=entry.venue.city if entry.venue else None,
        venueCountry=entry.venue.country if entry.venue else None,
        venueAvailabilityStatus=(
            entry.venue.availability_status if entry.venue else "not_set"
        ),
        sourceRfpId=entry.source_rfp_id,
        sourceRfpTitle=entry.source_rfp.title if entry.source_rfp else "Unknown",
        sourceRfpVenueId=entry.source_rfp_venue_id,
        desiredDatesStart=str(entry.desired_dates_start) if entry.desired_dates_start else None,
        desiredDatesEnd=str(entry.desired_dates_end) if entry.desired_dates_end else None,
        datesFlexible=entry.dates_flexible,
        attendanceMin=entry.attendance_min,
        attendanceMax=entry.attendance_max,
        eventType=entry.event_type,
        spaceRequirements=entry.space_requirements or [],
        status=entry.status,
        queuePosition=queue_position,
        holdOfferedAt=entry.hold_offered_at,
        holdExpiresAt=entry.hold_expires_at,
        holdRemainingSeconds=hold_remaining_seconds,
        holdReminderSent=entry.hold_reminder_sent,
        convertedRfpId=entry.converted_rfp_id,
        cancellationReason=entry.cancellation_reason,
        cancellationNotes=entry.cancellation_notes,
        expiresAt=entry.expires_at,
        stillInterestedSentAt=entry.still_interested_sent_at,
        stillInterestedResponded=entry.still_interested_responded,
        createdAt=entry.created_at,
        updatedAt=entry.updated_at,
    )


# --- Queries (API Contract Section 3.4) ---


def my_waitlist_entries(
    info: Info,
    status: Optional[str] = None,
    active_only: Optional[bool] = None,
    page: int = 1,
    page_size: int = 10,
) -> WaitlistEntryListResult:
    """
    List organizer's waitlist entries.
    Auth: Org member.
    """
    user, org_id = _get_user_org(info)
    db = info.context.db

    result = crud_venue_waitlist.list_waitlist_entries(
        db,
        org_id=org_id,
        status=status,
        active_only=active_only or False,
        page=page,
        page_size=page_size,
    )

    entries = [_entry_to_gql(db, e) for e in result["entries"]]

    return WaitlistEntryListResult(
        entries=entries,
        totalCount=result["pagination"]["total_count"],
        page=result["pagination"]["page"],
        pageSize=result["pagination"]["page_size"],
        totalPages=result["pagination"]["total_pages"],
    )


def waitlist_entry(info: Info, id: str) -> Optional[VenueWaitlistEntryType]:
    """
    Get single waitlist entry detail.
    Auth: Org member.
    """
    user, org_id = _get_user_org(info)
    db = info.context.db

    entry = crud_venue_waitlist.get_waitlist_entry(db, entry_id=id, org_id=org_id)

    if not entry:
        return None

    return _entry_to_gql(db, entry)


def venue_availability(info: Info, venue_id: str) -> VenueAvailabilityType:
    """
    Get venue's availability status and inference data.
    Auth: Venue owner only.
    """
    user, org_id = _get_user_org(info)
    db = info.context.db

    # Verify venue ownership
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    if venue.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = crud_venue_availability.get_venue_availability(db, venue_id=venue_id)

    # Convert signal summary
    signal_summary = None
    if result.get("signal_summary"):
        ss = result["signal_summary"]
        signal_summary = AvailabilitySignalSummary(
            periodDays=ss["period_days"],
            totalResponses=ss["total_responses"],
            confirmedCount=ss["confirmed_count"],
            tentativeCount=ss["tentative_count"],
            unavailableCount=ss["unavailable_count"],
            unavailableRatio=ss["unavailable_ratio"],
        )

    return VenueAvailabilityType(
        venueId=result["venue_id"],
        availabilityStatus=result["availability_status"],
        isManualOverride=result["is_manual_override"],
        lastInferredAt=result.get("last_inferred_at"),
        inferredStatus=result.get("inferred_status"),
        manualOverrideAt=result.get("manual_override_at"),
        signalSummary=signal_summary,
    )


def venue_availability_badge(info: Info, venue_id: str) -> AvailabilityBadge:
    """
    Get public availability badge.
    No auth required — public data.
    """
    db = info.context.db

    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    status_value = venue.availability_status or "not_set"

    # Color mapping
    colors = {
        "accepting_events": "green",
        "limited_availability": "yellow",
        "fully_booked": "red",
        "seasonal": "blue",
        "not_set": "gray",
    }

    # Label mapping
    labels = {
        "accepting_events": "Accepting Events",
        "limited_availability": "Limited Availability",
        "fully_booked": "Fully Booked",
        "seasonal": "Seasonal Venue",
        "not_set": "Status Unknown",
    }

    return AvailabilityBadge(
        venueId=venue_id,
        availabilityStatus=status_value,
        badgeColor=colors.get(status_value, "gray"),
        badgeLabel=labels.get(status_value, "Status Unknown"),
    )


def check_existing_waitlist(info: Info, venue_id: str) -> ExistingWaitlistCheck:
    """
    Check if the current user's organization already has a waitlist entry for this venue.
    Auth: Org member.
    """
    user, org_id = _get_user_org(info)
    db = info.context.db

    # Get active waitlist entry for this org and venue
    ACTIVE_STATUSES = {"waiting", "offered"}
    entry = (
        db.query(VenueWaitlistEntry)
        .filter(
            VenueWaitlistEntry.organization_id == org_id,
            VenueWaitlistEntry.venue_id == venue_id,
            VenueWaitlistEntry.status.in_(ACTIVE_STATUSES),
        )
        .first()
    )

    if not entry:
        return ExistingWaitlistCheck(
            alreadyOnWaitlist=False,
            queuePosition=None,
            waitlistId=None,
            status=None,
        )

    # Calculate queue position
    queue_position = crud_venue_waitlist.get_queue_position(db, entry=entry)

    return ExistingWaitlistCheck(
        alreadyOnWaitlist=True,
        queuePosition=queue_position,
        waitlistId=entry.id,
        status=entry.status,
    )
