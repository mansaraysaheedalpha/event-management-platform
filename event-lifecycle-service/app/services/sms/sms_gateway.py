"""
SMS gateway for check-in PIN delivery and SMS-based check-in.

Uses Africa's Talking API which covers 30+ African countries including
Kenya, Nigeria, South Africa, Ghana, Tanzania, Rwanda, Uganda, Senegal.

Cost: ~$0.01-0.03 per SMS depending on country.
Gracefully degrades when the SDK is not installed (dev environments).
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

AT_USERNAME = os.environ.get("AFRICASTALKING_USERNAME", "sandbox")
AT_API_KEY = os.environ.get("AFRICASTALKING_API_KEY", "")
AT_SHORTCODE = os.environ.get("AFRICASTALKING_SHORTCODE", "")


class SMSGateway:
    """Wrapper around Africa's Talking SMS API."""

    def __init__(self):
        self._client = None
        self._initialized = False

    @property
    def client(self):
        """Lazy-initialize the Africa's Talking client."""
        if not self._initialized:
            self._initialized = True
            if not AT_API_KEY:
                logger.info("AFRICASTALKING_API_KEY not set — SMS disabled")
                return None
            try:
                import africastalking
                africastalking.initialize(AT_USERNAME, AT_API_KEY)
                self._client = africastalking.SMS
                logger.info("Africa's Talking SMS gateway initialized")
            except ImportError:
                logger.warning(
                    "africastalking SDK not installed. "
                    "Run: pip install africastalking"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Africa's Talking: {e}")
        return self._client

    @staticmethod
    def _mask_phone(phone: str) -> str:
        """Mask phone number for logging: +254712345678 -> +254****5678"""
        if len(phone) <= 4:
            return "****"
        return phone[:4] + "****" + phone[-4:]

    def _send(self, phone_number: str, message: str) -> bool:
        """Send an SMS. Returns True on success, False on failure."""
        masked = self._mask_phone(phone_number)
        if not self.client:
            logger.debug(f"SMS skipped (gateway not configured) to {masked}")
            return False
        try:
            response = self.client.send(
                message,
                [phone_number],
                sender_id=AT_SHORTCODE or None,
            )
            logger.info(
                f"SMS sent to {masked}: "
                f"status={response.get('SMSMessageData', {}).get('Message', 'unknown')}"
            )
            return True
        except Exception as e:
            logger.error(f"SMS send failed to {masked}: {e}")
            return False

    def send_check_in_pin(
        self,
        phone_number: str,
        pin: str,
        event_name: str,
    ) -> bool:
        """Send check-in PIN to attendee via SMS."""
        shortcode_info = f" to {AT_SHORTCODE}" if AT_SHORTCODE else ""
        message = (
            f"Your check-in PIN for {event_name} is: {pin}\n"
            f"At the event, text CHECK {pin}{shortcode_info}"
        )
        return self._send(phone_number, message)

    def send_check_in_confirmation(
        self,
        phone_number: str,
        event_name: str,
    ) -> bool:
        """Send check-in confirmation after successful SMS check-in."""
        return self._send(
            phone_number,
            f"Checked in! Welcome to {event_name}.",
        )

    def send_check_in_failure(
        self,
        phone_number: str,
        reason: str,
    ) -> bool:
        """Send failure message when SMS check-in fails."""
        return self._send(
            phone_number,
            f"Check-in failed: {reason}. Please try again or show this message to staff.",
        )


sms_gateway = SMSGateway()
