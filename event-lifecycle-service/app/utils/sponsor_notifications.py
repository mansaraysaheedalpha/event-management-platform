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
import resend
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


def init_resend():
    """Initialize Resend with API key."""
    resend.api_key = settings.RESEND_API_KEY


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


# ==================== Booth Sync Functions ====================

def create_booth_for_sponsor(
    event_id: str,
    sponsor_id: str,
    organization_id: str,
    company_name: str,
    company_description: Optional[str] = None,
    company_logo_url: Optional[str] = None,
    tier: Optional[str] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a booth in the expo hall when a sponsor is added.

    This is called automatically when a sponsor is created. If no expo hall
    exists for the event, it gracefully returns without error (booth can
    be created manually later or when expo hall is set up).

    Args:
        event_id: The event ID
        sponsor_id: The sponsor's ID
        organization_id: The organization ID
        company_name: Sponsor's company name (used as booth name)
        company_description: Optional description
        company_logo_url: Optional logo URL
        tier: Sponsor tier (PLATINUM, GOLD, SILVER, BRONZE, STARTUP)
        category: Optional category for filtering

    Returns:
        Dict with success status and booth data or reason for skip
    """
    try:
        real_time_url = settings.REAL_TIME_SERVICE_URL_INTERNAL
        if not real_time_url:
            logger.warning("REAL_TIME_SERVICE_URL_INTERNAL not configured - skipping booth creation")
            return {"success": False, "reason": "SERVICE_NOT_CONFIGURED"}

        payload = {
            "eventId": event_id,
            "sponsorId": sponsor_id,
            "organizationId": organization_id,
            "companyName": company_name,
            "companyDescription": company_description,
            "companyLogoUrl": company_logo_url,
            "tier": tier,
            "category": category,
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{real_time_url}/internal/expo/sponsor-booth",
                json=payload,
                headers={"X-Internal-Api-Key": settings.INTERNAL_API_KEY}
            )

            if response.status_code in (200, 201):
                result = response.json()
                if result.get("boothCreated"):
                    logger.info(f"Auto-created booth for sponsor {sponsor_id}")
                else:
                    logger.info(f"Booth not created for sponsor {sponsor_id}: {result.get('reason')}")
                return result
            else:
                logger.error(f"Failed to create booth: HTTP {response.status_code} - {response.text}")
                return {"success": False, "reason": "API_ERROR", "statusCode": response.status_code}

    except httpx.TimeoutException:
        logger.error(f"Timeout creating booth for sponsor {sponsor_id}")
        return {"success": False, "reason": "TIMEOUT"}
    except Exception as e:
        logger.error(f"Error creating booth for sponsor {sponsor_id}: {e}")
        return {"success": False, "reason": "ERROR", "error": str(e)}


def update_booth_for_sponsor(
    event_id: str,
    sponsor_id: str,
    organization_id: str,
    company_name: Optional[str] = None,
    company_description: Optional[str] = None,
    company_logo_url: Optional[str] = None,
    tier: Optional[str] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update a booth when sponsor details are updated.

    Note: Booths don't have an isActive field. Use deactivate_booth_for_sponsor
    when archiving a sponsor.

    Args:
        event_id: The event ID
        sponsor_id: The sponsor's ID
        organization_id: The organization ID
        company_name: Updated company name
        company_description: Updated description
        company_logo_url: Updated logo URL
        tier: Updated tier
        category: Updated category

    Returns:
        Dict with success status and booth data
    """
    try:
        real_time_url = settings.REAL_TIME_SERVICE_URL_INTERNAL
        if not real_time_url:
            return {"success": False, "reason": "SERVICE_NOT_CONFIGURED"}

        payload = {
            "eventId": event_id,
            "sponsorId": sponsor_id,
            "organizationId": organization_id,
            "companyName": company_name,
            "companyDescription": company_description,
            "companyLogoUrl": company_logo_url,
            "tier": tier,
            "category": category,
        }

        # Remove None values to only send actual updates
        payload = {k: v for k, v in payload.items() if v is not None}

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{real_time_url}/internal/expo/sponsor-booth/update",
                json=payload,
                headers={"X-Internal-Api-Key": settings.INTERNAL_API_KEY}
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("boothUpdated"):
                    logger.info(f"Updated booth for sponsor {sponsor_id}")
                return result
            else:
                logger.error(f"Failed to update booth: HTTP {response.status_code}")
                return {"success": False, "reason": "API_ERROR"}

    except Exception as e:
        logger.error(f"Error updating booth for sponsor {sponsor_id}: {e}")
        return {"success": False, "reason": "ERROR", "error": str(e)}


def deactivate_booth_for_sponsor(event_id: str, sponsor_id: str) -> Dict[str, Any]:
    """
    Deactivate a booth when a sponsor is archived.

    Args:
        event_id: The event ID
        sponsor_id: The sponsor's ID

    Returns:
        Dict with success status
    """
    try:
        real_time_url = settings.REAL_TIME_SERVICE_URL_INTERNAL
        if not real_time_url:
            return {"success": False, "reason": "SERVICE_NOT_CONFIGURED"}

        payload = {
            "eventId": event_id,
            "sponsorId": sponsor_id,
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{real_time_url}/internal/expo/sponsor-booth/deactivate",
                json=payload,
                headers={"X-Internal-Api-Key": settings.INTERNAL_API_KEY}
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("boothDeactivated"):
                    logger.info(f"Deactivated booth for sponsor {sponsor_id}")
                return result
            else:
                logger.error(f"Failed to deactivate booth: HTTP {response.status_code}")
                return {"success": False, "reason": "API_ERROR"}

    except Exception as e:
        logger.error(f"Error deactivating booth for sponsor {sponsor_id}: {e}")
        return {"success": False, "reason": "ERROR", "error": str(e)}


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
        init_resend()

        # Build the invitation URL
        frontend_url = getattr(settings, 'FRONTEND_URL', 'https://eventdynamics.io')
        # Sanitize frontend_url: take first URL if comma-separated, strip whitespace
        if frontend_url and ',' in frontend_url:
            frontend_url = frontend_url.split(',')[0].strip()
        frontend_url = frontend_url.rstrip('/') if frontend_url else 'https://eventdynamics.io'
        invitation_url = f"{frontend_url}/sponsor/invitation/accept?token={invitation_token}"

        # Role display names
        role_names = {
            "admin": "Admin",
            "representative": "Representative",
            "booth_staff": "Booth Staff",
            "viewer": "Viewer"
        }
        role_display = role_names.get(role, role.title())

        personal_message_html = ""
        if personal_message:
            personal_message_html = f'''
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #FFD633;">
                <p style="margin: 0; font-style: italic; color: #555;">"{personal_message}"</p>
            </div>
            '''

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #0D1A3F 0%, #1a2f5f 100%); color: white; padding: 40px 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .invite-box {{ background: white; border: 2px solid #FFD633; padding: 25px; text-align: center; margin: 25px 0; border-radius: 12px; }}
                .role-badge {{ display: inline-block; background: #FFD633; color: #0D1A3F; padding: 8px 20px; border-radius: 20px; font-weight: bold; margin: 10px 0; }}
                .benefits {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .benefits ul {{ margin: 0; padding-left: 20px; }}
                .benefits li {{ margin: 8px 0; }}
                .cta-button {{ display: inline-block; background: #FFD633; color: #0D1A3F; padding: 15px 40px; text-decoration: none; border-radius: 30px; font-weight: bold; font-size: 16px; margin: 20px 0; }}
                .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; }}
                .expire-note {{ color: #666; font-size: 14px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>You're Invited!</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Join {sponsor_name} on Event Dynamics</p>
                </div>
                <div class="content">
                    <p>Hi there,</p>
                    <p><strong>{inviter_name}</strong> has invited you to join <strong>{sponsor_name}</strong> as a sponsor representative on Event Dynamics.</p>

                    {personal_message_html}

                    <div class="invite-box">
                        <p style="margin: 0 0 15px 0; color: #666;">Your Role</p>
                        <div class="role-badge">{role_display}</div>
                    </div>

                    <div class="benefits">
                        <h3 style="margin: 0 0 15px 0; color: #0D1A3F;">As a sponsor representative, you'll be able to:</h3>
                        <ul>
                            <li>📊 View and manage leads captured at events</li>
                            <li>🎯 Track engagement and intent scores</li>
                            <li>🔔 Receive real-time lead notifications</li>
                            <li>📤 Export lead data for your CRM</li>
                            <li>🏪 Manage your sponsor booth information</li>
                        </ul>
                    </div>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{invitation_url}" class="cta-button">Accept Invitation</a>
                    </div>

                    <p class="expire-note">
                        ⏰ This invitation expires in 7 days. If you didn't expect this invitation, you can safely ignore this email.
                    </p>

                    <p>Best regards,<br>The Event Dynamics Team</p>
                </div>
                <div class="footer">
                    <p>Event Dynamics - Where Events Come Alive</p>
                    <p style="margin-top: 10px;">
                        <a href="{invitation_url}" style="color: #0D1A3F; word-break: break-all; font-size: 11px;">{invitation_url}</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        subject = f"You've been invited to join {sponsor_name} on Event Dynamics"

        params = {
            "from": f"Event Dynamics <noreply@{settings.RESEND_FROM_DOMAIN}>",
            "to": [invitation_email],
            "subject": subject,
            "html": html_content,
        }

        response = resend.Emails.send(params)
        logger.info(f"Sponsor invitation email sent to {invitation_email} for {sponsor_name}")
        print(f"[EMAIL] Sponsor invitation sent to {invitation_email} for sponsor: {sponsor_name}")
        return True

    except Exception as e:
        logger.error(f"Error sending invitation email to {invitation_email}: {e}")
        print(f"[EMAIL ERROR] Failed to send invitation email to {invitation_email}: {e}")
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
        init_resend()

        # Intent level styling
        intent_colors = {
            "hot": "#EF4444",
            "warm": "#F97316",
            "cold": "#3B82F6"
        }
        intent_color = intent_colors.get(intent_level, "#6B7280")

        intent_emojis = {
            "hot": "🔥",
            "warm": "⭐",
            "cold": "❄️"
        }
        intent_emoji = intent_emojis.get(intent_level, "📍")

        frontend_url = getattr(settings, 'FRONTEND_URL', 'https://eventdynamics.io')
        # Sanitize frontend_url: take first URL if comma-separated, strip whitespace
        if frontend_url and ',' in frontend_url:
            frontend_url = frontend_url.split(',')[0].strip()
        frontend_url = frontend_url.rstrip('/') if frontend_url else 'https://eventdynamics.io'

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: {intent_color}; color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .lead-card {{ background: white; border-radius: 12px; padding: 25px; margin: 20px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
                .lead-name {{ font-size: 22px; font-weight: bold; margin: 0 0 5px 0; color: #0D1A3F; }}
                .lead-title {{ color: #666; margin: 0 0 15px 0; }}
                .intent-badge {{ display: inline-block; background: {intent_color}; color: white; padding: 6px 16px; border-radius: 20px; font-weight: bold; font-size: 14px; }}
                .detail-row {{ display: flex; padding: 8px 0; border-bottom: 1px solid #eee; }}
                .detail-label {{ color: #888; width: 100px; }}
                .detail-value {{ color: #333; font-weight: 500; }}
                .cta-button {{ display: inline-block; background: #FFD633; color: #0D1A3F; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; margin: 20px 0; }}
                .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{intent_emoji} New {intent_level.upper()} Lead Captured!</h1>
                </div>
                <div class="content">
                    <p>Great news! A new lead has been captured for <strong>{sponsor_name}</strong> at <strong>{event_name}</strong>.</p>

                    <div class="lead-card">
                        <p class="lead-name">{lead_name}</p>
                        <p class="lead-title">{f'{lead_title} at {lead_company}' if lead_title and lead_company else lead_company or lead_title or 'Contact'}</p>

                        <div style="margin: 20px 0;">
                            <span class="intent-badge">{intent_emoji} {intent_level.upper()} Intent</span>
                        </div>

                        <div style="margin-top: 20px;">
                            <div class="detail-row">
                                <span class="detail-label">Interaction</span>
                                <span class="detail-value">{interaction_type.replace('_', ' ').title()}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Event</span>
                                <span class="detail-value">{event_name}</span>
                            </div>
                        </div>
                    </div>

                    <div style="text-align: center;">
                        <a href="{frontend_url}/sponsor/leads" class="cta-button">View All Leads</a>
                    </div>

                    <p style="color: #888; font-size: 13px; margin-top: 20px;">
                        You're receiving this because lead notifications are enabled for {sponsor_name}.
                    </p>
                </div>
                <div class="footer">
                    <p>Event Dynamics - Where Events Come Alive</p>
                </div>
            </div>
        </body>
        </html>
        """

        subject = f"{intent_emoji} New {intent_level.upper()} Lead: {lead_name} - {event_name}"

        params = {
            "from": f"Event Dynamics <noreply@{settings.RESEND_FROM_DOMAIN}>",
            "to": [notification_email],
            "subject": subject,
            "html": html_content,
        }

        response = resend.Emails.send(params)
        logger.info(f"Lead notification email sent to {notification_email}")
        print(f"[EMAIL] Lead notification sent to {notification_email} for lead: {lead_name}")
        return True

    except Exception as e:
        logger.error(f"Error sending lead notification to {notification_email}: {e}")
        print(f"[EMAIL ERROR] Failed to send lead notification to {notification_email}: {e}")
        return False
