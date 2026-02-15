# app/utils/kafka_helpers.py
"""
Kafka helper functions for publishing events to topics.
Uses the singleton producer from app.core.kafka_producer.
"""
import logging
from app.core.kafka_producer import get_kafka_singleton

logger = logging.getLogger(__name__)

# Kafka Topics
TOPIC_WAITLIST_EVENTS = "waitlist.events.v1"
TOPIC_PAYMENT_EMAILS = "payment.emails.v1"


def publish_waitlist_offer_event(
    user_id: str,
    user_email: str,
    user_name: str,
    session_id: str,
    session_title: str,
    event_id: str,
    event_name: str,
    offer_token: str,
    offer_expires_at: str,
    position: int = None,
) -> bool:
    """
    Publish a waitlist offer event to Kafka.

    This event will be consumed by the email service to send the offer notification.

    Args:
        user_id: User's ID
        user_email: User's email address
        user_name: User's name
        session_id: Session ID
        session_title: Session title
        event_id: Event ID
        event_name: Event name
        offer_token: JWT token for accepting the offer
        offer_expires_at: ISO datetime string when offer expires
        position: Optional user's position in queue

    Returns:
        bool: True if published successfully, False otherwise
    """
    try:
        producer = get_kafka_singleton()

        if producer is None:
            logger.warning("Kafka producer unavailable, skipping event publish")
            return False

        event_data = {
            "type": "WAITLIST_OFFER",
            "userId": user_id,
            "userEmail": user_email,
            "userName": user_name,
            "sessionId": session_id,
            "sessionTitle": session_title,
            "eventId": event_id,
            "eventName": event_name,
            "offerToken": offer_token,
            "offerExpiresAt": offer_expires_at,
            "position": position,
        }

        future = producer.send(TOPIC_WAITLIST_EVENTS, value=event_data)
        # Wait for the send to complete (with timeout)
        future.get(timeout=10)

        logger.info(f"Published waitlist offer event for user {user_id}, session {session_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to publish waitlist offer event: {e}", exc_info=True)
        return False


def _publish_payment_email_event(event_type: str, payload: dict) -> bool:
    """
    Internal helper to publish a payment-related email event to Kafka.

    The event is fire-and-forget — if Kafka is unavailable, the email
    is sent directly via Resend as a fallback.

    Args:
        event_type: The email event type (e.g., "STRIPE_CONNECTED", "TICKET_CONFIRMATION")
        payload: The email payload data

    Returns:
        bool: True if published to Kafka successfully, False otherwise
    """
    try:
        producer = get_kafka_singleton()

        if producer is None:
            logger.warning(f"Kafka unavailable for {event_type}, falling back to direct send")
            return False

        event_data = {
            "type": event_type,
            **payload,
        }

        future = producer.send(TOPIC_PAYMENT_EMAILS, value=event_data)
        # Best-effort delivery: wait briefly for confirmation but don't block long.
        # A short timeout ensures we know if Kafka accepted the message so we
        # can fall back to direct email if it didn't.
        future.get(timeout=5)

        logger.info(f"Published payment email event: {event_type}")
        return True

    except Exception as e:
        logger.error(f"Failed to publish payment email event {event_type}: {e}", exc_info=True)
        return False


def publish_stripe_connected_email(
    to_email: str,
    organizer_name: str,
    organization_name: str,
    dashboard_url: str = "",
) -> bool:
    """Publish a stripe_connected email event to Kafka."""
    return _publish_payment_email_event("STRIPE_CONNECTED", {
        "toEmail": to_email,
        "organizerName": organizer_name,
        "organizationName": organization_name,
        "dashboardUrl": dashboard_url,
    })


def publish_stripe_restricted_email(
    to_email: str,
    organizer_name: str,
    organization_name: str,
    requirements_past_due: list[str] = None,
    resolve_url: str = "",
) -> bool:
    """Publish a stripe_restricted email event to Kafka."""
    return _publish_payment_email_event("STRIPE_RESTRICTED", {
        "toEmail": to_email,
        "organizerName": organizer_name,
        "organizationName": organization_name,
        "requirementsPastDue": requirements_past_due or [],
        "resolveUrl": resolve_url,
    })


def publish_ticket_confirmation_email(
    to_email: str,
    buyer_name: str,
    event_name: str,
    event_date: str,
    event_location: str = None,
    order_number: str = "",
    order_items: list[dict] = None,
    subtotal_cents: int = 0,
    platform_fee_cents: int = 0,
    total_cents: int = 0,
    fee_absorption: str = "absorb",
    currency: str = "USD",
) -> bool:
    """Publish a ticket_confirmation email event to Kafka."""
    return _publish_payment_email_event("TICKET_CONFIRMATION", {
        "toEmail": to_email,
        "buyerName": buyer_name,
        "eventName": event_name,
        "eventDate": event_date,
        "eventLocation": event_location,
        "orderNumber": order_number,
        "orderItems": order_items or [],
        "subtotalCents": subtotal_cents,
        "platformFeeCents": platform_fee_cents,
        "totalCents": total_cents,
        "feeAbsorption": fee_absorption,
        "currency": currency,
    })


def publish_new_ticket_sale_email(
    to_email: str,
    organizer_name: str,
    event_name: str,
    tickets_sold: int = 0,
    ticket_details: list[dict] = None,
    revenue_cents: int = 0,
    running_total_cents: int = 0,
    dashboard_url: str = "",
) -> bool:
    """Publish a new_ticket_sale email event to Kafka."""
    return _publish_payment_email_event("NEW_TICKET_SALE", {
        "toEmail": to_email,
        "organizerName": organizer_name,
        "eventName": event_name,
        "ticketsSold": tickets_sold,
        "ticketDetails": ticket_details or [],
        "revenueCents": revenue_cents,
        "runningTotalCents": running_total_cents,
        "dashboardUrl": dashboard_url,
    })


def publish_refund_confirmation_email(
    to_email: str,
    buyer_name: str,
    event_name: str,
    order_number: str = "",
    refund_amount_cents: int = 0,
    currency: str = "USD",
) -> bool:
    """Publish a refund_confirmation email event to Kafka."""
    return _publish_payment_email_event("REFUND_CONFIRMATION", {
        "toEmail": to_email,
        "buyerName": buyer_name,
        "eventName": event_name,
        "orderNumber": order_number,
        "refundAmountCents": refund_amount_cents,
        "currency": currency,
    })


def publish_payout_sent_email(
    to_email: str,
    organizer_name: str,
    payout_amount_cents: int = 0,
    currency: str = "USD",
    arrival_date: str = "",
    bank_last_four: str = "",
    stripe_dashboard_url: str = "",
) -> bool:
    """Publish a payout_sent email event to Kafka."""
    return _publish_payment_email_event("PAYOUT_SENT", {
        "toEmail": to_email,
        "organizerName": organizer_name,
        "payoutAmountCents": payout_amount_cents,
        "currency": currency,
        "arrivalDate": arrival_date,
        "bankLastFour": bank_last_four,
        "stripeDashboardUrl": stripe_dashboard_url,
    })


def publish_payout_failed_email(
    to_email: str,
    organizer_name: str,
    payout_amount_cents: int = 0,
    currency: str = "USD",
    failure_reason: str = "",
    stripe_dashboard_url: str = "",
) -> bool:
    """Publish a payout_failed email event to Kafka."""
    return _publish_payment_email_event("PAYOUT_FAILED", {
        "toEmail": to_email,
        "organizerName": organizer_name,
        "payoutAmountCents": payout_amount_cents,
        "currency": currency,
        "failureReason": failure_reason,
        "stripeDashboardUrl": stripe_dashboard_url,
    })