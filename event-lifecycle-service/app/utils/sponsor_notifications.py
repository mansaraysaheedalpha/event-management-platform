# app/utils/sponsor_notifications.py
"""
Sponsor notification utilities for email and real-time events.

This module handles:
- Sending invitation emails to sponsor representatives
- Sending lead notification emails to sponsors
- Emitting real-time events for lead captures
"""
import logging
import httpx
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


# ==================== Real-Time Event Emission ====================

def emit_lead_captured_event(sponsor_id: str, lead_data: Dict[str, Any]) -> bool:
    """
    Emit a real-time event when a lead is captured.

    This notifies connected sponsor dashboards via WebSocket.

    Args:
        sponsor_id: The sponsor's ID
        lead_data: Lead information to broadcast

    Returns:
        True if event was emitted successfully, False otherwise
    """
    try:
        real_time_url = settings.REAL_TIME_SERVICE_URL_INTERNAL
        if not real_time_url:
            logger.warning("REAL_TIME_SERVICE_URL_INTERNAL not configured")
            return False

        # Prepare the event payload
        payload = {
            "eventType": "LEAD_CAPTURED",
            "sponsorId": sponsor_id,
            "data": {
                "id": lead_data.get("id"),
                "userId": lead_data.get("user_id"),
                "userName": lead_data.get("user_name"),
                "userEmail": lead_data.get("user_email"),
                "userCompany": lead_data.get("user_company"),
                "userTitle": lead_data.get("user_title"),
                "intentScore": lead_data.get("intent_score"),
                "intentLevel": lead_data.get("intent_level"),
                "interactionType": lead_data.get("interaction_type"),
                "capturedAt": lead_data.get("created_at"),
            }
        }

        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                f"{real_time_url}/internal/sponsors/lead-event",
                json=payload,
                headers={"X-Internal-Api-Key": settings.INTERNAL_API_KEY}
            )

            if response.status_code == 200:
                logger.info(f"Lead captured event emitted for sponsor {sponsor_id}")
                return True
            else:
                logger.error(
                    f"Failed to emit lead event: HTTP {response.status_code}"
                )
                return False

    except httpx.TimeoutException:
        logger.error(f"Timeout emitting lead event for sponsor {sponsor_id}")
        return False
    except Exception as e:
        logger.error(f"Error emitting lead event: {e}")
        return False


def emit_lead_intent_updated_event(sponsor_id: str, lead_id: str, intent_data: Dict[str, Any]) -> bool:
    """
    Emit a real-time event when a lead's intent score is updated.

    Args:
        sponsor_id: The sponsor's ID
        lead_id: The lead's ID
        intent_data: Updated intent information

    Returns:
        True if event was emitted successfully, False otherwise
    """
    try:
        real_time_url = settings.REAL_TIME_SERVICE_URL_INTERNAL
        if not real_time_url:
            return False

        payload = {
            "eventType": "LEAD_INTENT_UPDATE",
            "sponsorId": sponsor_id,
            "data": {
                "leadId": lead_id,
                "intentScore": intent_data.get("intent_score"),
                "intentLevel": intent_data.get("intent_level"),
                "interactionCount": intent_data.get("interaction_count"),
            }
        }

        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                f"{real_time_url}/internal/sponsors/lead-event",
                json=payload,
                headers={"X-Internal-Api-Key": settings.INTERNAL_API_KEY}
            )
            return response.status_code == 200

    except Exception as e:
        logger.error(f"Error emitting intent update event: {e}")
        return False


# ==================== Email Notifications ====================

def send_sponsor_invitation_email(
    invitation_email: str,
    invitation_token: str,
    sponsor_name: str,
    inviter_name: str,
    role: str,
    personal_message: Optional[str] = None
) -> bool:
    """
    Send an invitation email to a prospective sponsor representative.

    Args:
        invitation_email: Recipient's email address
        invitation_token: Secure invitation token
        sponsor_name: Name of the sponsor company
        inviter_name: Name of the person sending the invitation
        role: Role being offered (admin, representative, etc.)
        personal_message: Optional personal message from inviter

    Returns:
        True if email was sent successfully, False otherwise
    """
    try:
        # Build the invitation URL
        frontend_url = getattr(settings, 'FRONTEND_URL', 'https://app.eventdynamics.com')
        invitation_url = f"{frontend_url}/sponsor/invitation/accept?token={invitation_token}"

        # Email content
        subject = f"You've been invited to join {sponsor_name} on Event Dynamics"

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>You're Invited!</h2>
            <p>Hi there,</p>
            <p><strong>{inviter_name}</strong> has invited you to join <strong>{sponsor_name}</strong>
               as a <strong>{role}</strong> on Event Dynamics.</p>

            {f'<p style="background: #f5f5f5; padding: 15px; border-radius: 8px; font-style: italic;">"{personal_message}"</p>' if personal_message else ''}

            <p>As a sponsor representative, you'll be able to:</p>
            <ul>
                <li>View and manage leads captured at events</li>
                <li>Track engagement and intent scores</li>
                <li>Access real-time notifications</li>
                <li>Export lead data for your CRM</li>
            </ul>

            <p style="text-align: center; margin: 30px 0;">
                <a href="{invitation_url}"
                   style="background: #4F46E5; color: white; padding: 12px 30px;
                          text-decoration: none; border-radius: 6px; font-weight: bold;">
                    Accept Invitation
                </a>
            </p>

            <p style="color: #666; font-size: 14px;">
                This invitation expires in 7 days. If you didn't expect this invitation,
                you can safely ignore this email.
            </p>

            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="color: #999; font-size: 12px;">
                Event Dynamics - Where Events Come Alive
            </p>
        </div>
        """

        # Send via email service
        return _send_email(invitation_email, subject, html_content)

    except Exception as e:
        logger.error(f"Error sending invitation email to {invitation_email}: {e}")
        return False


def send_lead_notification_email(
    notification_email: str,
    sponsor_name: str,
    lead_name: str,
    lead_company: Optional[str],
    lead_title: Optional[str],
    intent_level: str,
    interaction_type: str,
    event_name: str
) -> bool:
    """
    Send a notification email when a new lead is captured.

    Args:
        notification_email: Sponsor's notification email
        sponsor_name: Name of the sponsor company
        lead_name: Name of the lead
        lead_company: Lead's company (optional)
        lead_title: Lead's job title (optional)
        intent_level: hot, warm, or cold
        interaction_type: Type of interaction that captured the lead
        event_name: Name of the event

    Returns:
        True if email was sent successfully, False otherwise
    """
    try:
        # Intent level styling
        intent_colors = {
            "hot": "#EF4444",
            "warm": "#F97316",
            "cold": "#3B82F6"
        }
        intent_color = intent_colors.get(intent_level, "#6B7280")

        subject = f"New {intent_level.upper()} Lead: {lead_name} - {event_name}"

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: {intent_color}; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0;">New {intent_level.upper()} Lead Captured!</h2>
            </div>

            <div style="border: 1px solid #eee; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
                <h3 style="margin-top: 0;">{lead_name}</h3>
                {f'<p><strong>Company:</strong> {lead_company}</p>' if lead_company else ''}
                {f'<p><strong>Title:</strong> {lead_title}</p>' if lead_title else ''}
                <p><strong>Interaction:</strong> {interaction_type.replace('_', ' ').title()}</p>
                <p><strong>Event:</strong> {event_name}</p>

                <p style="text-align: center; margin: 25px 0;">
                    <a href="{getattr(settings, 'FRONTEND_URL', 'https://app.eventdynamics.com')}/sponsor/leads"
                       style="background: #4F46E5; color: white; padding: 12px 30px;
                              text-decoration: none; border-radius: 6px; font-weight: bold;">
                        View All Leads
                    </a>
                </p>
            </div>

            <p style="color: #999; font-size: 12px; text-align: center; margin-top: 20px;">
                You're receiving this because lead notifications are enabled for {sponsor_name}.
            </p>
        </div>
        """

        return _send_email(notification_email, subject, html_content)

    except Exception as e:
        logger.error(f"Error sending lead notification to {notification_email}: {e}")
        return False


def _send_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Internal function to send an email via the notification service.

    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML email content

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        # Check for email service configuration
        email_service_url = getattr(settings, 'EMAIL_SERVICE_URL', None)

        if not email_service_url:
            # Log the email content for development/testing
            logger.info(f"[EMAIL] To: {to_email}")
            logger.info(f"[EMAIL] Subject: {subject}")
            logger.info(f"[EMAIL] (Email service not configured - email logged only)")
            return True  # Return True in dev mode to not break the flow

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{email_service_url}/send",
                json={
                    "to": to_email,
                    "subject": subject,
                    "html": html_content
                },
                headers={"X-Internal-Api-Key": settings.INTERNAL_API_KEY}
            )

            if response.status_code == 200:
                logger.info(f"Email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send email: HTTP {response.status_code}")
                return False

    except Exception as e:
        logger.error(f"Error sending email to {to_email}: {e}")
        return False
