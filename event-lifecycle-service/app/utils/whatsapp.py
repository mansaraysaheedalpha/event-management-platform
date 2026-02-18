# app/utils/whatsapp.py
"""
SMS messaging via Africa's Talking API (fallback for WhatsApp).
Graceful fallback — failures are logged but never block the caller.
"""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_whatsapp_template(
    phone_number: str,
    template_name: str,
    template_params: list,
    *,
    deep_link: Optional[str] = None,
) -> bool:
    """
    Send an SMS notification via Africa's Talking (WhatsApp fallback).

    Args:
        phone_number: Recipient phone number (international format, e.g. +254...)
        template_name: Template name (converted to SMS message)
        template_params: Ordered list of template variable values
        deep_link: Optional deep link to include in message

    Returns:
        True if sent successfully, False otherwise
    """
    if not phone_number:
        logger.debug("No phone number provided, skipping SMS")
        return False

    # Check if Africa's Talking is configured
    if not settings.AFRICAS_TALKING_API_KEY or not settings.AFRICAS_TALKING_USERNAME:
        logger.debug("Africa's Talking not configured, skipping SMS")
        return False

    try:
        import africastalking

        # Initialize SDK
        africastalking.initialize(
            username=settings.AFRICAS_TALKING_USERNAME,
            api_key=settings.AFRICAS_TALKING_API_KEY,
        )
        sms = africastalking.SMS

        # Build message based on template
        message = _build_sms_message(template_name, template_params, deep_link)

        # Send SMS
        sender_id = getattr(settings, "AFRICAS_TALKING_SENDER_ID", None)
        response = sms.send(message, [phone_number], sender_id=sender_id)

        logger.info(
            f"SMS sent via Africa's Talking: to={phone_number}, "
            f"template={template_name}, response={response}"
        )
        return True

    except ImportError:
        logger.warning(
            "africastalking package not installed. Install with: pip install africastalking"
        )
        return False
    except Exception as e:
        logger.error(
            f"Failed to send SMS to {phone_number}: {e}",
            exc_info=True,
        )
        return False


def _build_sms_message(
    template_name: str, template_params: list, deep_link: Optional[str] = None
) -> str:
    """Build SMS message from template name and params."""
    # Map template names to SMS messages
    templates = {
        "waitlist_hold_offered": (
            f"🎉 Great news! You've been offered a hold for {template_params[0]}. "
            f"You have {template_params[1]} hours to respond. {template_params[2]}"
        ),
        "waitlist_hold_expiry_reminder": (
            f"⏰ Reminder: Your hold for {template_params[0]} expires in {template_params[1]} hours. "
            f"Respond now: {template_params[2]}"
        ),
        "waitlist_circuit_breaker": (
            f"ℹ️ The waitlist for {template_params[0]} has been paused due to low response rates. "
            f"We'll notify you when it resumes."
        ),
        "waitlist_auto_expired": (
            f"Your waitlist entry for {template_params[0]} has expired. "
            f"You can rejoin anytime from your dashboard."
        ),
    }

    message = templates.get(
        template_name,
        f"Notification: {' '.join(str(p) for p in template_params)}"
    )

    if deep_link and deep_link not in message:
        message += f" {deep_link}"

    return message
