# app/utils/rfp_notifications.py
"""
Channel-agnostic notification dispatcher for the RFP system.
Each function dispatches to Email (Resend), WhatsApp (Africa's Talking),
and In-app (Redis pub/sub) independently. Failures in one channel
do not block other channels.
"""
import json
import logging
from typing import Optional
from datetime import datetime, timezone

import resend

from app.core.config import settings
from app.db.redis import redis_client
from app.utils.whatsapp import send_whatsapp_template

logger = logging.getLogger(__name__)

# Configure Resend
if settings.RESEND_API_KEY:
    resend.api_key = settings.RESEND_API_KEY

FRONTEND_URL = settings.NEXT_PUBLIC_APP_URL


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


# ── Event: rfp.new_request ────────────────────────────────────────────

def dispatch_rfp_send_notifications(db, rfp) -> None:
    """Notify all venue owners that they've received a new RFP. Email + WhatsApp + In-app."""
    from app.models.venue import Venue

    for rv in rfp.venues:
        venue = db.query(Venue).filter(Venue.id == rv.venue_id).first()
        if not venue:
            continue

        deep_link = f"{FRONTEND_URL}/platform/venues/{venue.id}/rfps/{rfp.id}"

        # Format dates
        if rfp.preferred_dates_start and rfp.preferred_dates_end:
            dates_str = (
                f"{rfp.preferred_dates_start.strftime('%b %d')}-"
                f"{rfp.preferred_dates_end.strftime('%d, %Y')}"
            )
        elif rfp.preferred_dates_start:
            dates_str = rfp.preferred_dates_start.strftime("%b %d, %Y")
        else:
            dates_str = "Flexible"

        attendance_str = f"{rfp.attendance_min}-{rfp.attendance_max}"
        deadline_str = rfp.response_deadline.strftime("%b %d, %Y at %I:%M %p UTC")

        # Email
        subject = f"New Venue Request: {rfp.title}"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>New Venue Request Received</h2>
            <p>Your venue <strong>{venue.name}</strong> has received a new request:</p>
            <table style="border-collapse: collapse; width: 100%; margin: 16px 0;">
                <tr><td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Event</strong></td><td style="padding: 8px; border: 1px solid #e5e7eb;">{rfp.title}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Type</strong></td><td style="padding: 8px; border: 1px solid #e5e7eb;">{rfp.event_type}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Dates</strong></td><td style="padding: 8px; border: 1px solid #e5e7eb;">{dates_str}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Guests</strong></td><td style="padding: 8px; border: 1px solid #e5e7eb;">{attendance_str}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #e5e7eb;"><strong>Deadline</strong></td><td style="padding: 8px; border: 1px solid #e5e7eb;">{deadline_str}</td></tr>
            </table>
            <a href="{deep_link}" style="display: inline-block; background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Review & Respond</a>
        </div>
        """
        text = (
            f"New Venue Request for {venue.name}\n\n"
            f"Event: {rfp.title}\nType: {rfp.event_type}\nDates: {dates_str}\n"
            f"Guests: {attendance_str}\nDeadline: {deadline_str}\n\n"
            f"Review and respond: {deep_link}"
        )

        if venue.email:
            _send_email(venue.email, subject, html, text)

        # WhatsApp
        if venue.whatsapp:
            send_whatsapp_template(
                venue.whatsapp,
                "rfp_new_request",
                [venue.name, rfp.title, rfp.event_type, dates_str, attendance_str, deep_link, deadline_str],
            )

        # In-app
        _publish_inapp("rfp-notifications", {
            "event": "rfp.new_request",
            "venueId": venue.id,
            "orgId": venue.organization_id,
            "rfpId": rfp.id,
            "title": rfp.title,
        })


# ── Event: rfp.venue_responded ────────────────────────────────────────

def dispatch_venue_responded_notification(db, rfv, rfp) -> None:
    """Notify organizer that a venue has responded."""
    from app.models.venue import Venue

    venue = db.query(Venue).filter(Venue.id == rfv.venue_id).first()
    venue_name = venue.name if venue else "A venue"

    deep_link = f"{FRONTEND_URL}/platform/rfps/{rfp.id}"

    subject = f"Venue Response: {venue_name} responded to your RFP"
    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Venue Response Received</h2>
        <p><strong>{venue_name}</strong> has responded to your RFP: <em>{rfp.title}</em></p>
        <a href="{deep_link}" style="display: inline-block; background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">View Response</a>
    </div>
    """
    text = f"{venue_name} has responded to your RFP: {rfp.title}\n\nView response: {deep_link}"

    # In-app
    _publish_inapp("rfp-notifications", {
        "event": "rfp.venue_responded",
        "orgId": rfp.organization_id,
        "rfpId": rfp.id,
        "venueName": venue_name,
    })

    # Email — we don't have organizer email directly, so this would need
    # a cross-service call. For now, in-app is the primary channel.
    # TODO: Fetch organizer email from user service for email delivery


# ── Event: rfp.proposal_accepted ──────────────────────────────────────

def dispatch_proposal_accepted_notification(db, rfv) -> None:
    """Notify venue that their proposal was accepted. Email + WhatsApp + In-app."""
    from app.models.venue import Venue
    from app.models.rfp import RFP

    venue = db.query(Venue).filter(Venue.id == rfv.venue_id).first()
    rfp = db.query(RFP).filter(RFP.id == rfv.rfp_id).first()
    if not venue or not rfp:
        return

    deep_link = f"{FRONTEND_URL}/platform/venues/{venue.id}/rfps/{rfp.id}"

    subject = f"Congratulations! Your proposal for \"{rfp.title}\" was accepted"
    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Your Proposal Was Accepted!</h2>
        <p>Great news! Your proposal for <strong>{rfp.title}</strong> has been accepted by the organizer.</p>
        <a href="{deep_link}" style="display: inline-block; background: #16a34a; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">View Details</a>
    </div>
    """
    text = f"Your proposal for \"{rfp.title}\" was accepted!\n\nView details: {deep_link}"

    if venue.email:
        _send_email(venue.email, subject, html, text)

    if venue.whatsapp:
        send_whatsapp_template(
            venue.whatsapp,
            "rfp_proposal_accepted",
            [venue.name, rfp.title, deep_link],
        )

    _publish_inapp("rfp-notifications", {
        "event": "rfp.proposal_accepted",
        "venueId": venue.id,
        "orgId": venue.organization_id,
        "rfpId": rfp.id,
    })


# ── Event: rfp.proposal_declined ──────────────────────────────────────

def dispatch_proposal_declined_notification(db, rfv, reason=None) -> None:
    """Notify venue that their proposal was declined. Email + In-app."""
    from app.models.venue import Venue
    from app.models.rfp import RFP

    venue = db.query(Venue).filter(Venue.id == rfv.venue_id).first()
    rfp = db.query(RFP).filter(RFP.id == rfv.rfp_id).first()
    if not venue or not rfp:
        return

    reason_text = f"\n\nReason: {reason}" if reason else ""

    subject = f"RFP Update: \"{rfp.title}\""
    html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>RFP Update</h2>
        <p>The organizer has decided to go with another venue for <strong>{rfp.title}</strong>.</p>
        {"<p><strong>Reason:</strong> " + reason + "</p>" if reason else ""}
        <p>Thank you for your proposal. We hope to work together on future opportunities.</p>
    </div>
    """
    text = f"The organizer has decided to go with another venue for \"{rfp.title}\".{reason_text}"

    if venue.email:
        _send_email(venue.email, subject, html, text)

    _publish_inapp("rfp-notifications", {
        "event": "rfp.proposal_declined",
        "venueId": venue.id,
        "orgId": venue.organization_id,
        "rfpId": rfp.id,
    })


# ── Event: rfp.deadline_extended ──────────────────────────────────────

def dispatch_deadline_extended_notifications(db, rfp) -> None:
    """Notify non-responding venues of deadline extension. Email + WhatsApp."""
    from app.models.venue import Venue
    from app.models.rfp_venue import RFPVenue

    non_responders = (
        db.query(RFPVenue)
        .filter(
            RFPVenue.rfp_id == rfp.id,
            RFPVenue.status.in_(("received", "viewed")),
        )
        .all()
    )

    deadline_str = rfp.response_deadline.strftime("%b %d, %Y at %I:%M %p UTC")

    for rv in non_responders:
        venue = db.query(Venue).filter(Venue.id == rv.venue_id).first()
        if not venue:
            continue

        deep_link = f"{FRONTEND_URL}/platform/venues/{venue.id}/rfps/{rfp.id}"

        subject = f"Deadline Extended: {rfp.title}"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Deadline Extended</h2>
            <p>The deadline for <strong>{rfp.title}</strong> has been extended.</p>
            <p><strong>New deadline:</strong> {deadline_str}</p>
            <a href="{deep_link}" style="display: inline-block; background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Submit Your Proposal</a>
        </div>
        """
        text = f"Deadline extended for \"{rfp.title}\"\nNew deadline: {deadline_str}\n\nSubmit your proposal: {deep_link}"

        if venue.email:
            _send_email(venue.email, subject, html, text)

        if venue.whatsapp:
            send_whatsapp_template(
                venue.whatsapp,
                "rfp_deadline_extended",
                [venue.name, rfp.title, deadline_str, deep_link],
            )


# ── Event: rfp.deadline_reminder ──────────────────────────────────────

def dispatch_deadline_reminder_notifications(db, rfp) -> None:
    """Send 24h-before deadline reminders to non-responding venues."""
    from app.models.venue import Venue
    from app.models.rfp_venue import RFPVenue

    non_responders = (
        db.query(RFPVenue)
        .filter(
            RFPVenue.rfp_id == rfp.id,
            RFPVenue.status.in_(("received", "viewed")),
        )
        .all()
    )

    deadline_str = rfp.response_deadline.strftime("%b %d, %Y at %I:%M %p UTC")
    now = datetime.now(timezone.utc)
    hours_remaining = max(0, int((rfp.response_deadline - now).total_seconds() / 3600))

    for rv in non_responders:
        venue = db.query(Venue).filter(Venue.id == rv.venue_id).first()
        if not venue:
            continue

        deep_link = f"{FRONTEND_URL}/platform/venues/{venue.id}/rfps/{rfp.id}"

        subject = f"Reminder: Respond to \"{rfp.title}\" — {hours_remaining}h remaining"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Response Deadline Approaching</h2>
            <p>You have a pending venue request for <strong>{rfp.title}</strong>.</p>
            <p><strong>Deadline:</strong> {deadline_str} ({hours_remaining} hours remaining)</p>
            <a href="{deep_link}" style="display: inline-block; background: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Respond Now</a>
        </div>
        """
        text = f"Reminder: Respond to \"{rfp.title}\"\nDeadline: {deadline_str} ({hours_remaining}h remaining)\n\nRespond now: {deep_link}"

        if venue.email:
            _send_email(venue.email, subject, html, text)

        if venue.whatsapp:
            send_whatsapp_template(
                venue.whatsapp,
                "rfp_deadline_reminder",
                [venue.name, rfp.title, deadline_str, f"{hours_remaining} hours", deep_link],
            )


# ── Event: rfp.deadline_passed ────────────────────────────────────────

def dispatch_deadline_passed_notification(rfp, response_count: int, venue_count: int) -> None:
    """Notify organizer that the RFP deadline has passed."""
    deep_link = f"{FRONTEND_URL}/platform/rfps/{rfp.id}"

    _publish_inapp("rfp-notifications", {
        "event": "rfp.deadline_passed",
        "orgId": rfp.organization_id,
        "rfpId": rfp.id,
        "title": rfp.title,
        "responseCount": response_count,
        "venueCount": venue_count,
    })

    # TODO: Email to organizer (requires cross-service call for email)


# ── Event: rfp.all_responded ─────────────────────────────────────────

def dispatch_all_responded_notification(rfp) -> None:
    """Notify organizer that all venues have responded."""
    _publish_inapp("rfp-notifications", {
        "event": "rfp.all_responded",
        "orgId": rfp.organization_id,
        "rfpId": rfp.id,
        "title": rfp.title,
    })
