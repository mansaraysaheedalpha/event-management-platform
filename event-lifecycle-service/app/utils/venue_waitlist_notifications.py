# app/utils/venue_waitlist_notifications.py
"""
Multi-channel notification dispatchers for waitlist events.

Channels: In-app + Email + WhatsApp (where applicable)
Follows patterns from app/utils/rfp_notifications.py
"""
import json
import logging
from typing import Optional
from datetime import datetime, timezone

import resend

from app.models.venue_waitlist_entry import VenueWaitlistEntry
from app.utils.kafka_helpers import get_kafka_singleton
from app.core.config import settings
from app.db.redis import redis_client
from app.utils.whatsapp import send_whatsapp_template

logger = logging.getLogger(__name__)

# Configure Resend
if settings.RESEND_API_KEY:
    resend.api_key = settings.RESEND_API_KEY

FRONTEND_URL = settings.NEXT_PUBLIC_APP_URL


# ── Helper Functions ──────────────────────────────────────────────────

def _send_email(to: str, subject: str, html: str, text: str) -> bool:
    """Send email via Resend. Returns True on success."""
    if not settings.RESEND_API_KEY:
        logger.debug(f"Skipping email to {to} — RESEND_API_KEY not configured")
        return False
    try:
        params = {
            "from": f"GlobalConnect <noreply@{settings.RESEND_FROM_DOMAIN}>",
            "to": [to],
            "subject": subject,
            "html": html,
            "text": text,
        }
        resend.Emails.send(params)
        logger.info(f"Sent email to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}", exc_info=True)
        return False


def _publish_inapp(channel: str, payload: dict) -> bool:
    """Publish in-app notification via Redis pub/sub."""
    try:
        redis_client.publish(channel, json.dumps(payload))
        return True
    except Exception as e:
        logger.error(f"Failed to publish in-app notification: {e}", exc_info=True)
        return False


def _get_organizer_email(entry: VenueWaitlistEntry) -> Optional[str]:
    """Get organizer email from the entry's source RFP."""
    if entry.source_rfp and entry.source_rfp.organizer_email:
        return entry.source_rfp.organizer_email
    return None


def _get_venue_info(entry: VenueWaitlistEntry) -> tuple:
    """Get venue email and WhatsApp from entry."""
    if entry.venue:
        return entry.venue.email, entry.venue.whatsapp, entry.venue.name, entry.venue.organization_id
    return None, None, "Unknown Venue", None

# ── Notification Dispatchers ──────────────────────────────────────────


def notify_waitlist_joined(entry: VenueWaitlistEntry):
    """
    Notify organizer that they've joined a waitlist.
    Channels: In-app + Email
    """
    logger.info(f"Sending waitlist joined notification for entry {entry.id}")

    organizer_email = _get_organizer_email(entry)
    venue_name = entry.venue.name if entry.venue else "the venue"
    queue_position = entry.queue_position if hasattr(entry, 'queue_position') else "pending"

    deep_link = f"{FRONTEND_URL}/platform/waitlist"

    # In-app notification
    _publish_inapp("waitlist-notifications", {
        "event": "waitlist.joined",
        "orgId": entry.organization_id,
        "waitlistEntryId": entry.id,
        "venueId": entry.venue_id,
        "venueName": venue_name,
        "queuePosition": queue_position,
    })

    # Email notification
    if organizer_email:
        subject = f"You've joined the waitlist for {venue_name}"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Waitlist Confirmation</h2>
            <p>You've successfully joined the waitlist for <strong>{venue_name}</strong>.</p>
            <p><strong>Your position:</strong> #{queue_position}</p>
            <p>We'll notify you when a spot becomes available. You can view all your waitlist entries in your dashboard.</p>
            <a href="{deep_link}" style="display: inline-block; background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-top: 12px;">View Waitlists</a>
        </div>
        """
        text = f"You've joined the waitlist for {venue_name}.\n\nYour position: #{queue_position}\n\nView waitlists: {deep_link}"
        _send_email(organizer_email, subject, html, text)

    _emit_kafka("waitlist.joined_notification", entry)


def notify_hold_offered(entry: VenueWaitlistEntry):
    """
    Notify organizer that a hold has been offered (their turn in queue).
    Channels: In-app + Email + WhatsApp
    WhatsApp template: waitlist_hold_offered
    """
    logger.info(f"Sending hold offered notification for entry {entry.id}")

    organizer_email = _get_organizer_email(entry)
    venue_name = entry.venue.name if entry.venue else "the venue"

    # Calculate hold expiry time
    hold_hours = 48
    if entry.hold_expires_at:
        now = datetime.now(timezone.utc)
        remaining_seconds = max(0, (entry.hold_expires_at - now).total_seconds())
        hold_hours = int(remaining_seconds / 3600)

    deep_link = f"{FRONTEND_URL}/platform/waitlist/{entry.id}"

    # In-app notification (high priority)
    _publish_inapp("waitlist-notifications", {
        "event": "waitlist.hold_offered",
        "orgId": entry.organization_id,
        "waitlistEntryId": entry.id,
        "venueId": entry.venue_id,
        "venueName": venue_name,
        "holdExpiresAt": entry.hold_expires_at.isoformat() if entry.hold_expires_at else None,
        "priority": "high",
    })

    # Email notification
    if organizer_email:
        subject = f"🎉 You're up! Venue hold offered for {venue_name}"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #16a34a;">Great News! A Spot Opened Up</h2>
            <p>You've been offered an exclusive <strong>48-hour hold</strong> for <strong>{venue_name}</strong>.</p>
            <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px; margin: 16px 0;">
                <strong>⏰ Time remaining:</strong> {hold_hours} hours
            </div>
            <p><strong>Next steps:</strong></p>
            <ol>
                <li>Review the venue details</li>
                <li>Convert your hold to a formal venue request (RFP)</li>
                <li>Or decline if you're no longer interested</li>
            </ol>
            <a href="{deep_link}" style="display: inline-block; background: #16a34a; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; margin-top: 12px; font-weight: 600;">Claim Your Hold</a>
            <p style="color: #6b7280; font-size: 14px; margin-top: 24px;">If you don't take action within 48 hours, your hold will expire and the next person in line will be notified.</p>
        </div>
        """
        text = f"Great news! You've been offered a 48-hour hold for {venue_name}.\n\nTime remaining: {hold_hours} hours\n\nClaim your hold: {deep_link}\n\nIf you don't take action within 48 hours, your hold will expire."
        _send_email(organizer_email, subject, html, text)

    # WhatsApp notification (if phone number available from RFP)
    if entry.source_rfp and hasattr(entry.source_rfp, 'organizer_phone'):
        organizer_phone = entry.source_rfp.organizer_phone
        if organizer_phone:
            send_whatsapp_template(
                organizer_phone,
                "waitlist_hold_offered",
                [venue_name, str(hold_hours), deep_link],
            )

    _emit_kafka("waitlist.hold_offered_notification", entry)


def notify_hold_reminder(entry: VenueWaitlistEntry):
    """
    Send 24h-before reminder before hold expires.
    Channels: Email + WhatsApp
    WhatsApp template: waitlist_hold_reminder
    """
    logger.info(f"Sending hold reminder for entry {entry.id}")

    organizer_email = _get_organizer_email(entry)
    venue_name = entry.venue.name if entry.venue else "the venue"

    # Calculate remaining hours
    remaining_hours = 24
    if entry.hold_expires_at:
        now = datetime.now(timezone.utc)
        remaining_seconds = max(0, (entry.hold_expires_at - now).total_seconds())
        remaining_hours = int(remaining_seconds / 3600)

    deep_link = f"{FRONTEND_URL}/platform/waitlist/{entry.id}"

    # Email notification
    if organizer_email:
        subject = f"⏰ Reminder: Your hold for {venue_name} expires soon"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #dc2626;">Hold Expiring Soon</h2>
            <p>Your exclusive hold for <strong>{venue_name}</strong> will expire in <strong>{remaining_hours} hours</strong>.</p>
            <div style="background: #fee2e2; border-left: 4px solid #dc2626; padding: 12px; margin: 16px 0;">
                <strong>⏰ Don't miss out!</strong> Take action before your hold expires.
            </div>
            <p><strong>What happens next:</strong></p>
            <ul>
                <li>Convert to RFP to secure the venue</li>
                <li>Or decline to pass the opportunity to the next person</li>
            </ul>
            <a href="{deep_link}" style="display: inline-block; background: #dc2626; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; margin-top: 12px; font-weight: 600;">Take Action Now</a>
        </div>
        """
        text = f"Reminder: Your hold for {venue_name} expires in {remaining_hours} hours.\n\nTake action now: {deep_link}"
        _send_email(organizer_email, subject, html, text)

    # WhatsApp reminder
    if entry.source_rfp and hasattr(entry.source_rfp, 'organizer_phone'):
        organizer_phone = entry.source_rfp.organizer_phone
        if organizer_phone:
            send_whatsapp_template(
                organizer_phone,
                "waitlist_hold_reminder",
                [venue_name, str(remaining_hours), deep_link],
            )

    _emit_kafka("waitlist.hold_reminder_notification", entry)


def notify_hold_expired(entry: VenueWaitlistEntry):
    """
    Notify organizer that hold expired without action.
    Channels: In-app + Email
    """
    logger.info(f"Sending hold expired notification for entry {entry.id}")

    organizer_email = _get_organizer_email(entry)
    venue_name = entry.venue.name if entry.venue else "the venue"

    deep_link = f"{FRONTEND_URL}/platform/waitlist"

    # In-app notification
    _publish_inapp("waitlist-notifications", {
        "event": "waitlist.hold_expired",
        "orgId": entry.organization_id,
        "waitlistEntryId": entry.id,
        "venueId": entry.venue_id,
        "venueName": venue_name,
    })

    # Email notification
    if organizer_email:
        subject = f"Your hold for {venue_name} has expired"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Hold Expired</h2>
            <p>Your 48-hour hold for <strong>{venue_name}</strong> has expired.</p>
            <p>The opportunity has been passed to the next person in the waitlist.</p>
            <p>You can still join other waitlists or submit new venue requests directly.</p>
            <a href="{deep_link}" style="display: inline-block; background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-top: 12px;">Browse Venues</a>
        </div>
        """
        text = f"Your hold for {venue_name} has expired.\n\nThe opportunity has been passed to the next person in line.\n\nBrowse venues: {deep_link}"
        _send_email(organizer_email, subject, html, text)

    _emit_kafka("waitlist.hold_expired_notification", entry)


def notify_converted(entry: VenueWaitlistEntry):
    """
    Notify organizer of successful conversion to new RFP.
    Channels: In-app
    """
    logger.info(f"Sending conversion notification for entry {entry.id}")

    venue_name = entry.venue.name if entry.venue else "the venue"
    rfp_id = entry.converted_rfp_id

    deep_link = f"{FRONTEND_URL}/platform/rfps/{rfp_id}" if rfp_id else f"{FRONTEND_URL}/platform/rfps"

    # In-app notification
    _publish_inapp("waitlist-notifications", {
        "event": "waitlist.converted",
        "orgId": entry.organization_id,
        "waitlistEntryId": entry.id,
        "venueId": entry.venue_id,
        "venueName": venue_name,
        "rfpId": rfp_id,
        "deepLink": deep_link,
    })

    _emit_kafka("waitlist.converted_notification", entry)


def notify_position_changed(entry: VenueWaitlistEntry, new_position: int):
    """
    Notify organizer that queue position improved.
    Channels: In-app
    """
    logger.info(
        f"Sending position changed notification for entry {entry.id}, new position: {new_position}"
    )

    venue_name = entry.venue.name if entry.venue else "the venue"

    # In-app notification
    _publish_inapp("waitlist-notifications", {
        "event": "waitlist.position_changed",
        "orgId": entry.organization_id,
        "waitlistEntryId": entry.id,
        "venueId": entry.venue_id,
        "venueName": venue_name,
        "newPosition": new_position,
        "message": f"You've moved up to position #{new_position} for {venue_name}",
    })

    _emit_kafka(
        "waitlist.position_changed_notification", entry, {"new_position": new_position}
    )


def notify_still_interested(entry: VenueWaitlistEntry):
    """
    Send "still interested?" nudge at 60 days.
    Channels: Email
    """
    logger.info(f"Sending still interested nudge for entry {entry.id}")

    organizer_email = _get_organizer_email(entry)
    venue_name = entry.venue.name if entry.venue else "the venue"

    # Action link with entry ID to track response
    action_link = f"{FRONTEND_URL}/platform/waitlist/{entry.id}/confirm-interest"
    decline_link = f"{FRONTEND_URL}/platform/waitlist/{entry.id}/decline"

    # Email with action links
    if organizer_email:
        subject = f"Still interested in {venue_name}?"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Are You Still Interested?</h2>
            <p>You've been on the waitlist for <strong>{venue_name}</strong> for about 2 months.</p>
            <p>We want to make sure you're still interested in this venue. Please let us know:</p>
            <div style="margin: 24px 0;">
                <a href="{action_link}" style="display: inline-block; background: #16a34a; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; margin-right: 8px; font-weight: 600;">Yes, Still Interested</a>
                <a href="{decline_link}" style="display: inline-block; background: #6b7280; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 600;">No Longer Interested</a>
            </div>
            <p style="color: #6b7280; font-size: 14px; margin-top: 24px;">If we don't hear from you within 7 days, we'll automatically remove you from the waitlist to make room for others.</p>
        </div>
        """
        text = f"Are you still interested in {venue_name}?\n\nYou've been on the waitlist for about 2 months. Please confirm:\n\nYes, still interested: {action_link}\nNo longer interested: {decline_link}\n\nIf we don't hear from you within 7 days, we'll automatically remove you from the waitlist."
        _send_email(organizer_email, subject, html, text)

    _emit_kafka("waitlist.still_interested_nudge", entry)


def notify_auto_expired(entry: VenueWaitlistEntry):
    """
    Notify organizer that entry auto-expired.
    Channels: In-app + Email
    """
    logger.info(f"Sending auto-expired notification for entry {entry.id}")

    organizer_email = _get_organizer_email(entry)
    venue_name = entry.venue.name if entry.venue else "the venue"

    deep_link = f"{FRONTEND_URL}/platform/venues/{entry.venue_id}" if entry.venue_id else f"{FRONTEND_URL}/platform/venues"

    # In-app notification
    _publish_inapp("waitlist-notifications", {
        "event": "waitlist.auto_expired",
        "orgId": entry.organization_id,
        "waitlistEntryId": entry.id,
        "venueId": entry.venue_id,
        "venueName": venue_name,
    })

    # Email notification
    if organizer_email:
        reason = ""
        if entry.cancellation_reason == "nudge_declined":
            reason = "We didn't hear back from you when we checked if you were still interested."
        elif entry.cancellation_reason == "expired":
            reason = "The desired dates have passed or the maximum waitlist duration was reached."

        subject = f"Your waitlist entry for {venue_name} has expired"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Waitlist Entry Expired</h2>
            <p>Your waitlist entry for <strong>{venue_name}</strong> has been removed.</p>
            {f"<p><strong>Reason:</strong> {reason}</p>" if reason else ""}
            <p>You can submit a new venue request or join another waitlist anytime.</p>
            <a href="{deep_link}" style="display: inline-block; background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-top: 12px;">Browse Venues</a>
        </div>
        """
        text = f"Your waitlist entry for {venue_name} has expired.\n\n{reason}\n\nBrowse venues: {deep_link}"
        _send_email(organizer_email, subject, html, text)

    _emit_kafka("waitlist.auto_expired_notification", entry)


def notify_circuit_breaker(venue_id: str):
    """
    Notify venue owner that circuit breaker was triggered.
    Channels: In-app + Email
    """
    logger.info(f"Sending circuit breaker notification for venue {venue_id}")

    # Import here to avoid circular dependencies
    from app.models.venue import Venue
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        venue = db.query(Venue).filter(Venue.id == venue_id).first()
        if not venue:
            return

        venue_name = venue.name
        org_id = venue.organization_id

        deep_link = f"{FRONTEND_URL}/platform/venues/{venue_id}/waitlist-settings"

        # In-app notification to venue owner
        _publish_inapp("waitlist-notifications", {
            "event": "waitlist.circuit_breaker",
            "venueId": venue_id,
            "orgId": org_id,
            "venueName": venue_name,
            "priority": "high",
        })

        # Email to venue owner
        if venue.email:
            subject = f"⚠️ Waitlist paused for {venue_name}"
            html = f"""
            <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #dc2626;">Waitlist Paused — Action Required</h2>
                <p>The waitlist for <strong>{venue_name}</strong> has been automatically paused.</p>
                <div style="background: #fee2e2; border-left: 4px solid #dc2626; padding: 12px; margin: 16px 0;">
                    <strong>Why?</strong> We detected 3 consecutive people in your waitlist who didn't respond to hold offers.
                </div>
                <p><strong>What this means:</strong></p>
                <ul>
                    <li>No new holds will be offered from your waitlist</li>
                    <li>People remain on the waitlist, but it's paused</li>
                    <li>This prevents wasting opportunities on non-responsive organizers</li>
                </ul>
                <p><strong>What you should do:</strong></p>
                <ol>
                    <li>Review your venue availability settings</li>
                    <li>If you want to keep the waitlist active, click "Resume Waitlist" in your dashboard</li>
                    <li>Consider updating your venue availability status if you're not currently accepting events</li>
                </ol>
                <a href="{deep_link}" style="display: inline-block; background: #dc2626; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; margin-top: 12px; font-weight: 600;">Review Settings</a>
            </div>
            """
            text = f"Waitlist Paused for {venue_name}\n\nWe detected 3 consecutive no-responses in your waitlist. Please review your settings and resume if you want to continue offering holds.\n\nReview settings: {deep_link}"
            _send_email(venue.email, subject, html, text)

    finally:
        db.close()

    # Emit Kafka event
    try:
        producer = get_kafka_singleton()
        if producer:
            event_data = {
                "type": "WAITLIST_CIRCUIT_BREAKER",
                "venue_id": venue_id,
                "timestamp": str(datetime.now(timezone.utc)),
            }
            producer.send("waitlist-events", value=event_data)
    except Exception as e:
        logger.error(f"Failed to emit circuit breaker Kafka event: {e}")


def notify_circuit_breaker_resolved(venue_id: str):
    """
    Notify venue owner that circuit breaker was resolved.
    Channels: In-app + Email
    """
    logger.info(f"Sending circuit breaker resolved notification for venue {venue_id}")

    # Import here to avoid circular dependencies
    from app.models.venue import Venue
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        venue = db.query(Venue).filter(Venue.id == venue_id).first()
        if not venue:
            return

        venue_name = venue.name
        org_id = venue.organization_id

        deep_link = f"{FRONTEND_URL}/platform/venues/{venue_id}/waitlist"

        # In-app notification
        _publish_inapp("waitlist-notifications", {
            "event": "waitlist.circuit_breaker_resolved",
            "venueId": venue_id,
            "orgId": org_id,
            "venueName": venue_name,
        })

        # Email notification
        if venue.email:
            subject = f"✅ Waitlist resumed for {venue_name}"
            html = f"""
            <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #16a34a;">Waitlist Resumed</h2>
                <p>The waitlist for <strong>{venue_name}</strong> has been resumed.</p>
                <p>The next person in line will be offered a hold shortly.</p>
                <a href="{deep_link}" style="display: inline-block; background: #16a34a; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-top: 12px;">View Waitlist</a>
            </div>
            """
            text = f"Waitlist resumed for {venue_name}.\n\nThe next person in line will be offered a hold shortly.\n\nView waitlist: {deep_link}"
            _send_email(venue.email, subject, html, text)

    finally:
        db.close()

    # Emit Kafka event
    try:
        producer = get_kafka_singleton()
        if producer:
            event_data = {
                "type": "WAITLIST_CIRCUIT_BREAKER_RESOLVED",
                "venue_id": venue_id,
                "timestamp": str(datetime.now(timezone.utc)),
            }
            producer.send("waitlist-events", value=event_data)
    except Exception as e:
        logger.error(f"Failed to emit circuit breaker resolved Kafka event: {e}")


# Helper functions

def _emit_kafka(event_type: str, entry: VenueWaitlistEntry, metadata: dict = None):
    """Emit Kafka event for notification tracking."""
    try:
        producer = get_kafka_singleton()
        if not producer:
            logger.warning("Kafka producer unavailable, skipping event")
            return

        event_data = {
            "type": event_type,
            "waitlist_entry_id": entry.id,
            "organization_id": entry.organization_id,
            "venue_id": entry.venue_id,
            "status": entry.status,
            "metadata": metadata or {},
            "timestamp": str(datetime.now(timezone.utc)),
        }

        producer.send("waitlist-events", value=event_data)
        logger.debug(f"Emitted Kafka event: {event_type} for entry {entry.id}")
    except Exception as e:
        logger.error(f"Failed to emit Kafka event {event_type}: {e}")
