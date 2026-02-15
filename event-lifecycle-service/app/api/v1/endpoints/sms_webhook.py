# app/api/v1/endpoints/sms_webhook.py
"""
Incoming SMS webhook for Africa's Talking.

Handles SMS-based check-in for attendees without smartphones.
Attendees text "CHECK <PIN>" to the event shortcode and get
checked in automatically.

Africa's Talking POSTs form-encoded data:
  from: sender phone number (e.g., "+254712345678")
  to:   shortcode
  text: message body
  date: timestamp
  id:   message ID
"""

import os
import re
import time
import logging
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.crud.ticket_crud import ticket_crud
from app.services.sms.sms_gateway import sms_gateway

logger = logging.getLogger(__name__)


def _mask_phone(phone: str) -> str:
    """Mask phone number for logging: +254712345678 -> +254****5678"""
    if len(phone) <= 4:
        return "****"
    return phone[:4] + "****" + phone[-4:]

router = APIRouter()

AT_WEBHOOK_SECRET = os.environ.get("AFRICASTALKING_WEBHOOK_SECRET", "")

# Rate limiting: max 3 attempts per phone number per 10 minutes
SMS_RATE_LIMIT = 3
SMS_RATE_WINDOW = 600  # 10 minutes

# In-memory fallback (used when Redis is unavailable)
_sms_attempts: dict[str, list[float]] = defaultdict(list)

# Pattern: CHECK <6-digit PIN> or CHECKIN <6-digit PIN>
CHECK_IN_PATTERN = re.compile(
    r"^\s*(?:CHECK(?:\s*IN)?)\s+(\d{6})\s*$",
    re.IGNORECASE,
)


def _get_redis():
    """Get Redis client, returning None if unavailable."""
    try:
        from app.db.redis import redis_client
        redis_client.ping()
        return redis_client
    except Exception:
        return None


def _check_rate_limit(phone: str) -> bool:
    """Return True if the phone number is within rate limits.

    Uses Redis (shared across workers) when available, falling back
    to per-process in-memory tracking.
    """
    r = _get_redis()
    if r:
        key = f"sms_rate:{phone}"
        try:
            count = r.incr(key)
            if count == 1:
                r.expire(key, SMS_RATE_WINDOW)
            return count <= SMS_RATE_LIMIT
        except Exception:
            pass  # Fall through to in-memory

    # In-memory fallback
    now = time.time()
    attempts = _sms_attempts[phone]
    _sms_attempts[phone] = [t for t in attempts if now - t < SMS_RATE_WINDOW]
    if len(_sms_attempts[phone]) >= SMS_RATE_LIMIT:
        return False
    _sms_attempts[phone].append(now)
    return True


@router.post("/incoming")
async def handle_incoming_sms(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle incoming SMS from Africa's Talking.

    Validates webhook secret, parses CHECK <PIN> commands,
    performs check-in, and sends confirmation/failure SMS.
    """
    # Validate webhook secret if configured
    if AT_WEBHOOK_SECRET:
        header_secret = request.headers.get("X-AT-Webhook-Secret", "")
        if header_secret != AT_WEBHOOK_SECRET:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid webhook secret",
            )

    # Parse form data from Africa's Talking
    form = await request.form()
    sender = form.get("from", "")
    text = form.get("text", "")
    message_id = form.get("id", "unknown")

    logger.info(f"Incoming SMS [{message_id}] from {_mask_phone(sender)}")

    if not sender or not text:
        return {"status": "ignored", "reason": "empty sender or text"}

    # Rate limiting
    if not _check_rate_limit(sender):
        logger.warning(f"SMS rate limit hit for {_mask_phone(sender)}")
        sms_gateway.send_check_in_failure(sender, "Too many attempts. Try again later")
        return {"status": "rate_limited"}

    # Parse CHECK <PIN> command
    match = CHECK_IN_PATTERN.match(text.strip())
    if not match:
        sms_gateway.send_check_in_failure(
            sender,
            "Unrecognized command. Text CHECK followed by your 6-digit PIN",
        )
        return {"status": "unrecognized_command"}

    pin = match.group(1)

    # Search for the ticket across active events
    from datetime import datetime, timezone
    from app.models.ticket import Ticket
    from app.models.event import Event
    from sqlalchemy import and_

    now = datetime.now(timezone.utc)

    # Find ticket by PIN, joined with event to check it's still active
    ticket = (
        db.query(Ticket)
        .join(Event, Ticket.event_id == Event.id)
        .filter(
            and_(
                Ticket.check_in_pin == pin,
                Ticket.status.in_(["valid", "checked_in"]),
                Event.end_date >= now,
            )
        )
        .first()
    )

    if not ticket:
        logger.info(f"SMS check-in: PIN {pin} not found for sender {_mask_phone(sender)}")
        sms_gateway.send_check_in_failure(sender, "Invalid PIN")
        return {"status": "not_found"}

    # Check if already checked in
    if ticket.status == "checked_in":
        logger.info(f"SMS check-in: ticket {ticket.ticket_code} already checked in")
        sms_gateway.send_check_in_failure(sender, "Already checked in")
        return {"status": "already_checked_in"}

    # Perform check-in
    try:
        ticket_crud.check_in(
            db,
            ticket.id,
            checked_in_by="sms_check_in",
            location="SMS",
        )
        event_name = ticket.event.name if ticket.event else "the event"
        logger.info(
            f"SMS check-in success: {ticket.ticket_code} for {event_name} "
            f"from {_mask_phone(sender)}"
        )
        sms_gateway.send_check_in_confirmation(sender, event_name)
        return {"status": "checked_in", "ticketCode": ticket.ticket_code}

    except ValueError as e:
        logger.warning(f"SMS check-in failed for {ticket.ticket_code}: {e}")
        sms_gateway.send_check_in_failure(sender, "Check-in failed")
        return {"status": "error"}
