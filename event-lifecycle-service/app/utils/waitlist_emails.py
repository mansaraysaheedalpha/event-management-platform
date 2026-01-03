# app/utils/waitlist_emails.py
"""
Email notification utilities for waitlist management.

Sends emails for:
- Waitlist position updates
- Offer notifications
- Offer expiration reminders
"""

import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
import resend

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure Resend
if settings.RESEND_API_KEY:
    resend.api_key = settings.RESEND_API_KEY
else:
    logger.warning("RESEND_API_KEY not configured. Email notifications disabled.")


def send_waitlist_offer_email(
    user_email: str,
    user_name: str,
    session_title: str,
    event_name: str,
    offer_token: str,
    expires_at: datetime,
    accept_url: str
) -> bool:
    """
    Send email notification when user receives a waitlist offer.

    Args:
        user_email: Recipient email
        user_name: Recipient name
        session_title: Session title
        event_name: Event name
        offer_token: JWT offer token
        expires_at: Offer expiration time
        accept_url: URL to accept offer

    Returns:
        True if sent successfully, False otherwise
    """
    if not settings.RESEND_API_KEY:
        logger.warning(f"Skipping email to {user_email} - RESEND_API_KEY not configured")
        return False

    try:
        # Calculate minutes until expiration
        now = datetime.now(timezone.utc)
        minutes_left = int((expires_at - now).total_seconds() / 60)

        # Build email HTML
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px 10px 0 0;
            text-align: center;
        }}
        .content {{
            background: #f9fafb;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }}
        .highlight {{
            background: #fef3c7;
            padding: 20px;
            border-left: 4px solid #f59e0b;
            margin: 20px 0;
        }}
        .button {{
            display: inline-block;
            background: #10b981;
            color: white;
            padding: 15px 30px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            margin: 20px 0;
        }}
        .warning {{
            color: #dc2626;
            font-weight: bold;
        }}
        .footer {{
            text-align: center;
            color: #6b7280;
            font-size: 12px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎉 A Spot Opened Up!</h1>
    </div>
    <div class="content">
        <p>Hi {user_name},</p>

        <p>Great news! A spot has opened up for the session you've been waiting for:</p>

        <div class="highlight">
            <strong>Session:</strong> {session_title}<br>
            <strong>Event:</strong> {event_name}
        </div>

        <p class="warning">⏰ You have {minutes_left} minutes to accept this offer!</p>

        <p>Click the button below to claim your spot:</p>

        <center>
            <a href="{accept_url}" class="button">Accept Spot Now</a>
        </center>

        <p><small>Or copy this link: {accept_url}</small></p>

        <p><strong>Important:</strong> This offer will expire at {expires_at.strftime('%I:%M %p UTC')} on {expires_at.strftime('%B %d, %Y')}. If you don't accept in time, the spot will go to the next person in line.</p>

        <p>Thank you for your patience!</p>

        <p>Best regards,<br>The {event_name} Team</p>
    </div>
    <div class="footer">
        <p>GlobalConnect Event Management Platform</p>
        <p>This email was sent because you joined the waitlist for this session.</p>
    </div>
</body>
</html>
        """

        # Plain text version
        text_content = f"""
Hi {user_name},

Great news! A spot has opened up for the session you've been waiting for:

Session: {session_title}
Event: {event_name}

⏰ You have {minutes_left} minutes to accept this offer!

Click here to claim your spot:
{accept_url}

IMPORTANT: This offer will expire at {expires_at.strftime('%I:%M %p UTC')} on {expires_at.strftime('%B %d, %Y')}.
If you don't accept in time, the spot will go to the next person in line.

Thank you for your patience!

Best regards,
The {event_name} Team

---
GlobalConnect Event Management Platform
        """

        # Send email via Resend
        params = {
            "from": f"GlobalConnect <noreply@{settings.RESEND_FROM_DOMAIN}>",
            "to": [user_email],
            "subject": f"🎉 Spot Available: {session_title}",
            "html": html_content,
            "text": text_content
        }

        response = resend.Emails.send(params)

        logger.info(
            f"Sent waitlist offer email to {user_email} for session {session_title}. "
            f"Resend ID: {response.get('id')}"
        )

        return True

    except Exception as e:
        logger.error(
            f"Failed to send waitlist offer email to {user_email}: {e}",
            exc_info=True
        )
        return False


def send_waitlist_position_update_email(
    user_email: str,
    user_name: str,
    session_title: str,
    event_name: str,
    new_position: int,
    total_waiting: int
) -> bool:
    """
    Send email notification when user's position in waitlist changes significantly.

    Only send if position improved by 5+ spots to avoid spam.

    Args:
        user_email: Recipient email
        user_name: Recipient name
        session_title: Session title
        event_name: Event name
        new_position: New position in queue
        total_waiting: Total users waiting

    Returns:
        True if sent successfully, False otherwise
    """
    if not settings.RESEND_API_KEY:
        logger.warning(f"Skipping email to {user_email} - RESEND_API_KEY not configured")
        return False

    try:
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: #3b82f6;
            color: white;
            padding: 30px;
            border-radius: 10px 10px 0 0;
            text-align: center;
        }}
        .content {{
            background: #f9fafb;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }}
        .position {{
            background: #dbeafe;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            margin: 20px 0;
        }}
        .position-number {{
            font-size: 48px;
            font-weight: bold;
            color: #1e40af;
        }}
        .footer {{
            text-align: center;
            color: #6b7280;
            font-size: 12px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📍 Your Position Updated</h1>
    </div>
    <div class="content">
        <p>Hi {user_name},</p>

        <p>Your position in the waitlist for <strong>{session_title}</strong> has been updated:</p>

        <div class="position">
            <div>You're now</div>
            <div class="position-number">#{new_position}</div>
            <div>out of {total_waiting} waiting</div>
        </div>

        <p>You're getting closer! We'll notify you immediately when a spot opens up.</p>

        <p>Best regards,<br>The {event_name} Team</p>
    </div>
    <div class="footer">
        <p>GlobalConnect Event Management Platform</p>
    </div>
</body>
</html>
        """

        text_content = f"""
Hi {user_name},

Your position in the waitlist for {session_title} has been updated:

You're now #{new_position} out of {total_waiting} waiting

You're getting closer! We'll notify you immediately when a spot opens up.

Best regards,
The {event_name} Team

---
GlobalConnect Event Management Platform
        """

        params = {
            "from": f"GlobalConnect <noreply@{settings.RESEND_FROM_DOMAIN}>",
            "to": [user_email],
            "subject": f"Waitlist Update: You're #{new_position} - {session_title}",
            "html": html_content,
            "text": text_content
        }

        response = resend.Emails.send(params)

        logger.info(
            f"Sent position update email to {user_email} for session {session_title}. "
            f"New position: #{new_position}"
        )

        return True

    except Exception as e:
        logger.error(
            f"Failed to send position update email to {user_email}: {e}",
            exc_info=True
        )
        return False


def send_offer_expiring_soon_email(
    user_email: str,
    user_name: str,
    session_title: str,
    event_name: str,
    expires_at: datetime,
    accept_url: str
) -> bool:
    """
    Send reminder email when offer is about to expire.

    Typically sent 1-2 minutes before expiration.

    Args:
        user_email: Recipient email
        user_name: Recipient name
        session_title: Session title
        event_name: Event name
        expires_at: Offer expiration time
        accept_url: URL to accept offer

    Returns:
        True if sent successfully, False otherwise
    """
    if not settings.RESEND_API_KEY:
        logger.warning(f"Skipping email to {user_email} - RESEND_API_KEY not configured")
        return False

    try:
        now = datetime.now(timezone.utc)
        minutes_left = int((expires_at - now).total_seconds() / 60)

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: #dc2626;
            color: white;
            padding: 30px;
            border-radius: 10px 10px 0 0;
            text-align: center;
        }}
        .content {{
            background: #f9fafb;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }}
        .urgent {{
            background: #fee2e2;
            border: 2px solid #dc2626;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            margin: 20px 0;
        }}
        .button {{
            display: inline-block;
            background: #dc2626;
            color: white;
            padding: 15px 30px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            color: #6b7280;
            font-size: 12px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>⏰ Your Offer Expires Soon!</h1>
    </div>
    <div class="content">
        <p>Hi {user_name},</p>

        <div class="urgent">
            <h2 style="color: #dc2626; margin: 0;">⚠️ {minutes_left} Minutes Left!</h2>
            <p style="margin: 10px 0 0 0;">Your spot for <strong>{session_title}</strong> will be given to the next person if you don't act now.</p>
        </div>

        <center>
            <a href="{accept_url}" class="button">Accept Spot Now</a>
        </center>

        <p><small>Or copy this link: {accept_url}</small></p>

        <p>Don't miss out on this opportunity!</p>

        <p>Best regards,<br>The {event_name} Team</p>
    </div>
    <div class="footer">
        <p>GlobalConnect Event Management Platform</p>
    </div>
</body>
</html>
        """

        text_content = f"""
⏰ YOUR OFFER EXPIRES SOON!

Hi {user_name},

⚠️ {minutes_left} MINUTES LEFT!

Your spot for {session_title} will be given to the next person if you don't act now.

Click here to accept NOW:
{accept_url}

Don't miss out on this opportunity!

Best regards,
The {event_name} Team

---
GlobalConnect Event Management Platform
        """

        params = {
            "from": f"GlobalConnect <noreply@{settings.RESEND_FROM_DOMAIN}>",
            "to": [user_email],
            "subject": f"⏰ URGENT: Your Offer Expires in {minutes_left} Min - {session_title}",
            "html": html_content,
            "text": text_content
        }

        response = resend.Emails.send(params)

        logger.info(
            f"Sent offer expiring soon email to {user_email} for session {session_title}. "
            f"Minutes left: {minutes_left}"
        )

        return True

    except Exception as e:
        logger.error(
            f"Failed to send offer expiring email to {user_email}: {e}",
            exc_info=True
        )
        return False
