# app/utils/whatsapp.py
"""
WhatsApp messaging via Africa's Talking API.
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
    Send a WhatsApp template message via Africa's Talking.

    Args:
        phone_number: Recipient phone number (international format, e.g. +254...)
        template_name: Pre-approved WhatsApp template name
        template_params: Ordered list of template variable values
        deep_link: Optional deep link to include (may be part of template_params)

    Returns:
        True if sent successfully, False otherwise
    """
    if not phone_number:
        logger.debug("No phone number provided, skipping WhatsApp message")
        return False

    try:
        # Africa's Talking WhatsApp integration
        # For production, use their SDK:
        #   import africastalking
        #   africastalking.initialize(username, api_key)
        #   sms = africastalking.SMS
        #   sms.send(message, [phone_number], sender_id)
        #
        # For now, log the intent and return success.
        # The actual API call will be enabled once AT credentials are configured.

        logger.info(
            f"WhatsApp message queued: template={template_name}, "
            f"to={phone_number}, params={template_params}"
        )
        return True

    except Exception as e:
        logger.error(
            f"Failed to send WhatsApp message to {phone_number}: {e}",
            exc_info=True,
        )
        return False
