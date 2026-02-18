# app/graphql/venue_waitlist_mutations.py
"""GraphQL Venue Waitlist mutations — called from the main Mutation class."""
from typing import Optional
from datetime import datetime, timezone
from strawberry.types import Info
from fastapi import HTTPException

from ..crud import crud_venue_waitlist, crud_venue_availability, crud_rfp_venue
from ..models.venue import Venue
from .venue_waitlist_types import (
    VenueWaitlistEntryType,
    JoinWaitlistResponse,
    ConvertHoldResponse,
    CancelWaitlistResponse,
    RespondStillInterestedResponse,
    SetAvailabilityResponse,
    ClearOverrideResponse,
    ResolveCircuitBreakerResponse,
    AvailabilityStatusEnum,
    CancellationReasonEnum,
)
from .venue_waitlist_queries import _entry_to_gql
from ..utils.waitlist_cascade import trigger_cascade
from ..utils import venue_waitlist_notifications
from ..utils.kafka_helpers import get_kafka_singleton


def _get_user_org(info: Info) -> tuple:
    """Extract user and org_id from context."""
    user = info.context.user
    if not user or not user.get("orgId"):
        raise HTTPException(status_code=403, detail="Not authorized")
    return user, user["orgId"]


def _check_venue_owner(db, org_id: str, venue_id: str):
    """Verify that the current user owns the venue."""
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    if venue.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return venue


# --- Mutations (API Contract Section 3.5) ---


def join_venue_waitlist(
    info: Info,
    rfp_venue_id: str,
) -> JoinWaitlistResponse:
    """
    Join a waitlist for an unavailable venue.
    Auth: Org member.
    Triggers: waitlist.joined_notification
    """
    user, org_id = _get_user_org(info)
    db = info.context.db

    # Validate that the RFP venue exists and belongs to the user's org
    rfp_venue = crud_rfp_venue.get(db, id=rfp_venue_id)
    if not rfp_venue:
        raise HTTPException(status_code=404, detail="RFP venue not found")
    if rfp_venue.rfp.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        entry = crud_venue_waitlist.create_waitlist_entry(
            db, org_id=org_id, rfp_venue_id=rfp_venue_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Send notification
    try:
        venue_waitlist_notifications.notify_waitlist_joined(entry)
    except Exception as e:
        # Log but don't fail
        pass

    # Convert to GraphQL type
    entry_gql = _entry_to_gql(db, entry)

    return JoinWaitlistResponse(
        success=True,
        waitlistEntry=entry_gql,
        message="Successfully joined venue waitlist",
    )


def convert_waitlist_hold(
    info: Info,
    waitlist_entry_id: str,
) -> ConvertHoldResponse:
    """
    Convert a hold into a new RFP.
    Auth: Org member.
    Validates hold status and creates new RFP.
    Triggers: cascade to next person, conversion notification
    """
    user, org_id = _get_user_org(info)
    db = info.context.db

    # Get the entry and validate ownership
    entry = crud_venue_waitlist.get_waitlist_entry(
        db, entry_id=waitlist_entry_id, org_id=org_id
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")

    try:
        new_rfp = crud_venue_waitlist.convert_hold(db, entry=entry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    venue_id = entry.venue_id

    # Send notification
    try:
        venue_waitlist_notifications.notify_converted(entry)
    except Exception as e:
        pass

    # Trigger cascade to next person
    trigger_cascade(db, venue_id)

    return ConvertHoldResponse(
        success=True,
        newRfpId=new_rfp.id,
        waitlistEntryId=waitlist_entry_id,
        message="Hold converted to new RFP successfully",
    )


def cancel_waitlist_entry(
    info: Info,
    waitlist_entry_id: str,
    reason: CancellationReasonEnum,
    notes: Optional[str] = None,
) -> CancelWaitlistResponse:
    """
    Cancel a waitlist entry.
    Auth: Org member.
    Triggers: cascade to next person
    """
    user, org_id = _get_user_org(info)
    db = info.context.db

    # Get the entry and validate ownership
    entry = crud_venue_waitlist.get_waitlist_entry(
        db, entry_id=waitlist_entry_id, org_id=org_id
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")

    venue_id = entry.venue_id

    try:
        crud_venue_waitlist.cancel_entry(
            db, entry=entry, reason=reason.value, notes=notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Trigger cascade to next person
    trigger_cascade(db, venue_id)

    return CancelWaitlistResponse(
        success=True,
        waitlistEntryId=waitlist_entry_id,
        message="Waitlist entry cancelled successfully",
    )


def respond_still_interested(
    info: Info,
    waitlist_entry_id: str,
    still_interested: bool,
) -> RespondStillInterestedResponse:
    """
    Respond to a "still interested?" nudge.
    Auth: Org member.
    If still_interested=False, cancels the entry.
    """
    user, org_id = _get_user_org(info)
    db = info.context.db

    # Get the entry and validate ownership
    entry = crud_venue_waitlist.get_waitlist_entry(
        db, entry_id=waitlist_entry_id, org_id=org_id
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")

    venue_id = entry.venue_id

    try:
        crud_venue_waitlist.respond_still_interested(
            db, entry=entry, still_interested=still_interested
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # If declined, trigger cascade
    if not still_interested:
        trigger_cascade(db, venue_id)

    message = (
        "Confirmed continued interest in waitlist"
        if still_interested
        else "Waitlist entry cancelled"
    )

    return RespondStillInterestedResponse(
        success=True,
        waitlistEntryId=waitlist_entry_id,
        stillInterested=still_interested,
        message=message,
    )


def set_venue_availability(
    info: Info,
    venue_id: str,
    availability_status: AvailabilityStatusEnum,
) -> SetAvailabilityResponse:
    """
    Manually set venue availability status (creates override).
    Auth: Venue owner only.
    If status='accepting_events', triggers cascade.
    """
    user, org_id = _get_user_org(info)
    db = info.context.db

    # Verify venue ownership
    _check_venue_owner(db, org_id, venue_id)

    try:
        venue = crud_venue_availability.set_venue_availability(
            db,
            venue_id=venue_id,
            org_id=org_id,
            status=availability_status.value,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Record signal
    signal_type = (
        "manual_available"
        if availability_status.value == "accepting_events"
        else "manual_unavailable"
    )
    try:
        crud_venue_availability.record_signal(
            db,
            venue_id=venue_id,
            signal_type=signal_type,
            metadata={"set_by": user.get("sub")},
        )
    except Exception as e:
        pass

    # Emit Kafka event
    try:
        producer = get_kafka_singleton()
        if producer:
            event_data = {
                "event_type": "venue.availability_manual_set",
                "venue_id": venue_id,
                "new_status": availability_status.value,
                "set_by": org_id,
                "timestamp": str(datetime.now(timezone.utc)),
            }
            producer.send("waitlist-events", value=event_data)
    except Exception as e:
        pass

    # If accepting_events, trigger cascade
    if availability_status.value == "accepting_events":
        trigger_cascade(db, venue_id)

    return SetAvailabilityResponse(
        success=True,
        venueId=venue_id,
        availabilityStatus=availability_status,
        isManualOverride=True,
        manualOverrideAt=venue.availability_manual_override_at,
    )


def clear_venue_availability_override(
    info: Info,
    venue_id: str,
) -> ClearOverrideResponse:
    """
    Clear manual override, revert to inference-driven status.
    Auth: Venue owner only.
    """
    user, org_id = _get_user_org(info)
    db = info.context.db

    # Verify venue ownership
    _check_venue_owner(db, org_id, venue_id)

    try:
        venue = crud_venue_availability.clear_manual_override(
            db, venue_id=venue_id, org_id=org_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ClearOverrideResponse(
        success=True,
        venueId=venue_id,
        availabilityStatus=AvailabilityStatusEnum(venue.availability_status),
        isManualOverride=False,
        revertedToInferred=True,
    )


def resolve_waitlist_circuit_breaker(
    info: Info,
    venue_id: str,
) -> ResolveCircuitBreakerResponse:
    """
    Venue owner confirms the waitlist should remain active after circuit breaker pause.
    Resets the consecutive no-response counter and resumes the cascade.
    Auth: Venue owner only.
    """
    user, org_id = _get_user_org(info)
    db = info.context.db

    # Verify venue ownership
    _check_venue_owner(db, org_id, venue_id)

    try:
        result = crud_venue_waitlist.resolve_circuit_breaker(db, venue_id=venue_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Emit Kafka event
    try:
        producer = get_kafka_singleton()
        if producer:
            event_data = {
                "event_type": "waitlist.circuit_breaker_resolved",
                "venue_id": venue_id,
                "resolved_by": org_id,
                "timestamp": str(datetime.now(timezone.utc)),
            }
            producer.send("waitlist-events", value=event_data)
    except Exception as e:
        pass

    # Notify venue owner
    try:
        venue_waitlist_notifications.notify_circuit_breaker_resolved(venue_id)
    except Exception as e:
        pass

    # Trigger cascade to resume
    trigger_cascade(db, venue_id)

    # Check if next entry was offered
    next_entry = crud_venue_waitlist.get_next_waiting_entry(db, venue_id=venue_id)
    next_entry_offered = None
    if next_entry and next_entry.status == "offered":
        next_entry_offered = next_entry.id

    return ResolveCircuitBreakerResponse(
        success=True,
        venueId=venue_id,
        circuitBreakerResolved=True,
        cascadeResumed=True,
        nextEntryOffered=next_entry_offered,
    )
