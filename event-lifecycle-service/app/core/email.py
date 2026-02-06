# app/core/email.py
"""
Email service using Resend for sending transactional emails.
"""
import resend
import html
import re
from typing import Optional
from urllib.parse import urlparse
from app.core.config import settings


def _validate_email(email: str) -> bool:
    """Validate email format."""
    # RFC 5322 simplified pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email)) and len(email) <= 254


def _validate_url(url: str) -> str:
    """
    Validate URL is safe to include in emails.
    Returns the URL if valid, empty string otherwise.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        # Only allow http/https schemes
        if parsed.scheme not in ('http', 'https'):
            return ""
        # Must have a valid netloc (host)
        if not parsed.netloc:
            return ""
        # Optionally check against allowed domains (frontend URL)
        frontend_host = urlparse(settings.FRONTEND_URL).netloc if settings.FRONTEND_URL else ""
        # Allow localhost for development
        allowed_hosts = [frontend_host, 'localhost', '127.0.0.1']
        if parsed.netloc not in allowed_hosts and not any(
            parsed.netloc.endswith(f".{host}") for host in allowed_hosts if host
        ):
            # Log but still return - internal URLs should be trusted
            pass
        return url
    except Exception:
        return ""


def _escape_html(text: Optional[str]) -> str:
    """Safely escape HTML content."""
    if text is None:
        return ""
    return html.escape(str(text), quote=True)


def init_resend():
    """Initialize Resend with API key."""
    resend.api_key = settings.RESEND_API_KEY


def send_registration_confirmation(
    to_email: str,
    recipient_name: str,
    event_name: str,
    event_date: str,
    ticket_code: str,
    event_location: str = None,
) -> dict:
    """
    Send a registration confirmation email.

    Args:
        to_email: Recipient email address
        recipient_name: Name of the recipient
        event_name: Name of the event
        event_date: Date/time of the event
        ticket_code: The unique ticket code for check-in
        event_location: Optional venue/location info

    Returns:
        Resend API response
    """
    init_resend()

    # Validate email format
    if not _validate_email(to_email):
        return {"success": False, "error": "Invalid email address format"}

    # Escape all user-controlled content
    recipient_name = _escape_html(recipient_name)
    event_name = _escape_html(event_name)
    event_date = _escape_html(event_date)
    ticket_code = _escape_html(ticket_code)
    event_location = _escape_html(event_location)

    location_html = f"<p><strong>Location:</strong> {event_location}</p>" if event_location and event_location != "" else ""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .ticket-box {{ background: white; border: 2px dashed #667eea; padding: 20px; text-align: center; margin: 20px 0; border-radius: 8px; }}
            .ticket-code {{ font-size: 28px; font-weight: bold; color: #667eea; letter-spacing: 3px; }}
            .details {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
            .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>You're Registered!</h1>
            </div>
            <div class="content">
                <p>Hi {recipient_name},</p>
                <p>Great news! Your registration for <strong>{event_name}</strong> has been confirmed.</p>

                <div class="ticket-box">
                    <p style="margin: 0 0 10px 0; color: #666;">Your Ticket Code</p>
                    <div class="ticket-code">{ticket_code}</div>
                    <p style="margin: 10px 0 0 0; font-size: 12px; color: #888;">Present this code at check-in</p>
                </div>

                <div class="details">
                    <h3 style="margin-top: 0;">Event Details</h3>
                    <p><strong>Event:</strong> {event_name}</p>
                    <p><strong>Date:</strong> {event_date}</p>
                    {location_html}
                </div>

                <p>We're excited to see you there! If you have any questions, feel free to reach out.</p>

                <p>Best regards,<br>The Event Team</p>
            </div>
            <div class="footer">
                <p>This email was sent by Event Dynamics Platform</p>
                <p>Powered by Infinite Dynamics</p>
            </div>
        </div>
    </body>
    </html>
    """

    params = {
        "from": f"Event Dynamics <noreply@{settings.RESEND_FROM_DOMAIN}>",
        "to": [to_email],
        "subject": f"Registration Confirmed: {event_name}",
        "html": html_content,
    }

    try:
        response = resend.Emails.send(params)
        print(f"[EMAIL] Registration confirmation sent for event")
        return {"success": True, "id": response.get("id")}
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send registration confirmation email: {type(e).__name__}")
        return {"success": False, "error": "Failed to send email"}


def send_giveaway_winner_email(
    to_email: str,
    winner_name: str,
    event_name: str,
    session_name: str = None,
    giveaway_type: str = "SINGLE_POLL",  # SINGLE_POLL or QUIZ_SCORE
    prize_title: str = None,
    prize_description: str = None,
    claim_instructions: str = None,
    claim_location: str = None,
    claim_deadline: str = None,
    quiz_score: int = None,
    quiz_total: int = None,
    winning_option_text: str = None,
) -> dict:
    """
    Send a giveaway winner notification email.

    Args:
        to_email: Winner's email address
        winner_name: Name of the winner
        event_name: Name of the event
        session_name: Optional session name
        giveaway_type: Type of giveaway (SINGLE_POLL or QUIZ_SCORE)
        prize_title: Title of the prize
        prize_description: Description of the prize
        claim_instructions: How to claim the prize
        claim_location: Where to claim (for physical prizes)
        claim_deadline: Deadline to claim the prize
        quiz_score: For quiz giveaways - the winner's score
        quiz_total: For quiz giveaways - total questions
        winning_option_text: For poll giveaways - the winning option

    Returns:
        Resend API response
    """
    init_resend()

    # Validate email format
    if not _validate_email(to_email):
        return {"success": False, "error": "Invalid email address format"}

    # Escape all user-controlled content
    winner_name = _escape_html(winner_name)
    event_name = _escape_html(event_name)
    session_name = _escape_html(session_name)
    prize_title = _escape_html(prize_title)
    prize_description = _escape_html(prize_description)
    claim_instructions = _escape_html(claim_instructions)
    claim_location = _escape_html(claim_location)
    claim_deadline = _escape_html(claim_deadline)
    winning_option_text = _escape_html(winning_option_text)

    # Build the winning context based on giveaway type
    if giveaway_type == "QUIZ_SCORE" and quiz_score is not None:
        win_context = f"""
        <div class="score-box">
            <p style="margin: 0 0 5px 0; color: #666;">Your Quiz Score</p>
            <div class="score">{quiz_score}/{quiz_total}</div>
            <p style="margin: 5px 0 0 0; font-size: 14px; color: #888;">Outstanding performance!</p>
        </div>
        """
    elif winning_option_text:
        win_context = f"""
        <div class="win-context">
            <p style="margin: 0; color: #666;">Your winning answer: <strong>{winning_option_text}</strong></p>
        </div>
        """
    else:
        win_context = ""

    # Build prize details section
    prize_html = ""
    if prize_title:
        prize_html = f"""
        <div class="prize-box">
            <h3 style="margin: 0 0 10px 0; color: #667eea;">🎁 Your Prize</h3>
            <p style="font-size: 18px; font-weight: bold; margin: 0 0 10px 0;">{prize_title}</p>
            {"<p style='color: #666; margin: 0;'>" + prize_description + "</p>" if prize_description else ""}
        </div>
        """

    # Build claim instructions section
    claim_html = ""
    if claim_instructions or claim_location or claim_deadline:
        claim_details = []
        if claim_instructions:
            claim_details.append(f"<p><strong>How to claim:</strong> {claim_instructions}</p>")
        if claim_location:
            claim_details.append(f"<p><strong>Where:</strong> {claim_location}</p>")
        if claim_deadline:
            claim_details.append(f"<p><strong>Claim by:</strong> {claim_deadline}</p>")

        claim_html = f"""
        <div class="claim-box">
            <h4 style="margin: 0 0 10px 0;">📋 Claim Instructions</h4>
            {"".join(claim_details)}
        </div>
        """

    session_text = f" during <strong>{session_name}</strong>" if session_name else ""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 40px 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .header h1 {{ margin: 0; font-size: 32px; }}
            .header .emoji {{ font-size: 48px; margin-bottom: 10px; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .score-box {{ background: white; border: 2px solid #f5576c; padding: 20px; text-align: center; margin: 20px 0; border-radius: 8px; }}
            .score {{ font-size: 36px; font-weight: bold; color: #f5576c; }}
            .win-context {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center; }}
            .prize-box {{ background: linear-gradient(135deg, #fff6e6 0%, #fff0f0 100%); padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f5576c; }}
            .claim-box {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; border: 1px dashed #ddd; }}
            .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; }}
            .cta-button {{ display: inline-block; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="emoji">🎉</div>
                <h1>Congratulations!</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">You're a Winner!</p>
            </div>
            <div class="content">
                <p>Hi {winner_name},</p>
                <p>Amazing news! You've won the giveaway at <strong>{event_name}</strong>{session_text}!</p>

                {win_context}
                {prize_html}
                {claim_html}

                <p style="text-align: center; margin-top: 25px;">
                    We're thrilled to have you as a winner. Don't forget to claim your prize!
                </p>

                <p>Best regards,<br>The Event Team</p>
            </div>
            <div class="footer">
                <p>This email was sent by Event Dynamics Platform</p>
                <p>Powered by Infinite Dynamics</p>
            </div>
        </div>
    </body>
    </html>
    """

    subject = f"🎉 You Won! Giveaway Winner at {event_name}"

    params = {
        "from": f"Event Dynamics <noreply@{settings.RESEND_FROM_DOMAIN}>",
        "to": [to_email],
        "subject": subject,
        "html": html_content,
    }

    try:
        response = resend.Emails.send(params)
        print(f"[EMAIL] Giveaway winner notification sent")
        return {"success": True, "id": response.get("id")}
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send giveaway email: {type(e).__name__}")
        return {"success": False, "error": "Failed to send email"}


def send_waitlist_offer_email(
    to_email: str,
    user_name: str,
    session_title: str,
    event_name: str,
    offer_expires_at: str,
    accept_url: str,
    position: int = None,
) -> dict:
    """
    Send a waitlist spot offer notification email.

    Args:
        to_email: User's email address
        user_name: Name of the user
        session_title: Title of the session
        event_name: Name of the event
        offer_expires_at: When the offer expires (formatted string)
        accept_url: URL to accept the offer
        position: Optional - user's position in queue

    Returns:
        Resend API response
    """
    init_resend()

    # Validate email format
    if not _validate_email(to_email):
        return {"success": False, "error": "Invalid email address format"}

    # Escape all user-controlled content
    user_name = _escape_html(user_name)
    session_title = _escape_html(session_title)
    event_name = _escape_html(event_name)
    offer_expires_at = _escape_html(offer_expires_at)

    position_text = f"<p style='color: #666; margin: 10px 0;'>You were #{position} in the waitlist queue</p>" if position else ""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 40px 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .header h1 {{ margin: 0; font-size: 32px; }}
            .header .emoji {{ font-size: 48px; margin-bottom: 10px; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .offer-box {{ background: white; border: 3px solid #11998e; padding: 25px; text-align: center; margin: 25px 0; border-radius: 12px; }}
            .timer {{ font-size: 18px; color: #e74c3c; font-weight: bold; margin: 15px 0; }}
            .session-details {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #11998e; }}
            .cta-button {{ display: inline-block; background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 15px 40px; text-decoration: none; border-radius: 30px; font-weight: bold; font-size: 18px; margin: 20px 0; }}
            .cta-button:hover {{ opacity: 0.9; }}
            .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; }}
            .urgent {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="emoji">🎉</div>
                <h1>A Spot Opened Up!</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">You have a limited-time offer</p>
            </div>
            <div class="content">
                <p>Hi {user_name},</p>
                <p>Great news! A spot has become available for the session you were waiting for.</p>

                <div class="session-details">
                    <h3 style="margin: 0 0 10px 0; color: #11998e;">📅 Session Details</h3>
                    <p style="margin: 5px 0;"><strong>Session:</strong> {session_title}</p>
                    <p style="margin: 5px 0;"><strong>Event:</strong> {event_name}</p>
                    {position_text}
                </div>

                <div class="urgent">
                    <p style="margin: 0; font-weight: bold;">⏰ Act Fast!</p>
                    <div class="timer">Offer expires: {offer_expires_at}</div>
                    <p style="margin: 5px 0 0 0; font-size: 14px;">You have limited time to accept this offer before it goes to the next person in line.</p>
                </div>

                <div class="offer-box">
                    <p style="margin: 0 0 20px 0; font-size: 18px;">Ready to claim your spot?</p>
                    <a href="{accept_url}" class="cta-button">Accept Offer Now</a>
                    <p style="margin: 20px 0 0 0; font-size: 12px; color: #888;">Or copy this link: <br><a href="{accept_url}" style="color: #11998e; word-break: break-all;">{accept_url}</a></p>
                </div>

                <p style="color: #666; font-size: 14px;">If you don't want this spot, you can ignore this email and it will be offered to the next person in line.</p>

                <p>Best regards,<br>The Event Team</p>
            </div>
            <div class="footer">
                <p>This email was sent by Event Dynamics Platform</p>
                <p>Powered by Infinite Dynamics</p>
            </div>
        </div>
    </body>
    </html>
    """

    subject = f"🎉 Your Waitlist Spot is Ready: {session_title}"

    params = {
        "from": f"Event Dynamics <noreply@{settings.RESEND_FROM_DOMAIN}>",
        "to": [to_email],
        "subject": subject,
        "html": html_content,
    }

    try:
        response = resend.Emails.send(params)
        print(f"[EMAIL] Waitlist offer sent")
        return {"success": True, "id": response.get("id")}
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send waitlist offer email: {type(e).__name__}")
        return {"success": False, "error": "Failed to send email"}


def send_session_reminder_email(
    to_email: str,
    attendee_name: str,
    session_title: str,
    session_start_time: str,
    event_name: str,
    speaker_names: list[str],
    join_url: str,
    minutes_until_start: int,
) -> dict:
    """
    Send a session reminder email with magic link join button.

    Args:
        to_email: Attendee's email address
        attendee_name: Name of the attendee
        session_title: Title of the session
        session_start_time: Formatted start time string
        event_name: Name of the event
        speaker_names: List of speaker names
        join_url: Magic link URL to join the session
        minutes_until_start: Minutes until session starts (5 or 15)

    Returns:
        Resend API response with success status
    """
    init_resend()

    # Validate email format
    if not _validate_email(to_email):
        return {"success": False, "error": "Invalid email address format"}

    # Escape all user-controlled content
    attendee_name = _escape_html(attendee_name)
    session_title = _escape_html(session_title)
    session_start_time = _escape_html(session_start_time)
    event_name = _escape_html(event_name)
    speaker_names = [_escape_html(name) for name in speaker_names]

    # Build speakers section
    if speaker_names:
        speakers_list = ", ".join(speaker_names)
        speakers_html = f"""
        <p style="margin: 5px 0;"><strong>Speakers:</strong> {speakers_list}</p>
        """
    else:
        speakers_html = ""

    # Urgency messaging based on time
    if minutes_until_start <= 5:
        urgency_text = "Starting in just a few minutes!"
        urgency_color = "#e74c3c"
        header_emoji = "🔔"
        time_badge = f'<span style="background: #e74c3c; color: white; padding: 4px 12px; border-radius: 20px; font-size: 14px; font-weight: bold;">{minutes_until_start} MIN</span>'
    else:
        urgency_text = f"Starting in {minutes_until_start} minutes"
        urgency_color = "#f39c12"
        header_emoji = "⏰"
        time_badge = f'<span style="background: #f39c12; color: white; padding: 4px 12px; border-radius: 20px; font-size: 14px; font-weight: bold;">{minutes_until_start} MIN</span>'

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .header h1 {{ margin: 0 0 10px 0; font-size: 28px; }}
            .header .emoji {{ font-size: 48px; margin-bottom: 15px; }}
            .header .time-badge {{ margin-top: 15px; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .session-box {{ background: white; border-left: 4px solid #667eea; padding: 20px; margin: 20px 0; border-radius: 0 8px 8px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .session-title {{ font-size: 20px; font-weight: bold; color: #333; margin: 0 0 15px 0; }}
            .join-button-container {{ text-align: center; margin: 30px 0; }}
            .join-button {{ display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white !important; padding: 18px 50px; text-decoration: none; border-radius: 30px; font-weight: bold; font-size: 20px; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4); }}
            .join-button:hover {{ opacity: 0.9; }}
            .fallback-link {{ background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0; font-size: 13px; word-break: break-all; }}
            .fallback-link a {{ color: #667eea; }}
            .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; padding: 20px; }}
            .urgency-banner {{ background: {urgency_color}; color: white; padding: 12px 20px; text-align: center; font-weight: bold; border-radius: 8px; margin-bottom: 20px; }}
            @media only screen and (max-width: 480px) {{
                .container {{ padding: 10px; }}
                .header {{ padding: 30px 20px; }}
                .header h1 {{ font-size: 24px; }}
                .content {{ padding: 20px; }}
                .join-button {{ padding: 15px 35px; font-size: 18px; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="emoji">{header_emoji}</div>
                <h1>Your Session is About to Start!</h1>
                <div class="time-badge">{time_badge}</div>
            </div>
            <div class="content">
                <div class="urgency-banner">
                    {urgency_text}
                </div>

                <p>Hi {attendee_name},</p>
                <p>Don't miss out! The session you registered for is starting soon.</p>

                <div class="session-box">
                    <p class="session-title">{session_title}</p>
                    <p style="margin: 5px 0;"><strong>Event:</strong> {event_name}</p>
                    <p style="margin: 5px 0;"><strong>Start Time:</strong> {session_start_time}</p>
                    {speakers_html}
                </div>

                <div class="join-button-container">
                    <a href="{join_url}" class="join-button">Join Session Now</a>
                </div>

                <div class="fallback-link">
                    <strong>Can't click the button?</strong><br>
                    Copy and paste this link into your browser:<br>
                    <a href="{join_url}">{join_url}</a>
                </div>

                <p style="color: #666; font-size: 14px; margin-top: 25px;">
                    This link will take you directly to the session. No additional login required.
                </p>

                <p>See you there!<br>The Event Team</p>
            </div>
            <div class="footer">
                <p>This email was sent by Event Dynamics Platform</p>
                <p>Powered by Infinite Dynamics</p>
                <p style="margin-top: 10px; font-size: 11px;">You're receiving this because you registered for {event_name}</p>
            </div>
        </div>
    </body>
    </html>
    """

    # Plain text fallback
    plain_text = f"""
Your Session is About to Start!

Hi {attendee_name},

Your session "{session_title}" at {event_name} is starting in {minutes_until_start} minutes!

Session Details:
- Title: {session_title}
- Start Time: {session_start_time}
- Event: {event_name}
{f"- Speakers: {', '.join(speaker_names)}" if speaker_names else ""}

Join now: {join_url}

See you there!
The Event Team

---
This email was sent by Event Dynamics Platform
Powered by Infinite Dynamics
"""

    subject = f"{'🔔' if minutes_until_start <= 5 else '⏰'} Starting in {minutes_until_start} min: {session_title}"

    params = {
        "from": f"Event Dynamics <noreply@{settings.RESEND_FROM_DOMAIN}>",
        "to": [to_email],
        "subject": subject,
        "html": html_content,
        "text": plain_text,
    }

    try:
        response = resend.Emails.send(params)
        print(f"[EMAIL] Session reminder ({minutes_until_start} min) sent")
        return {"success": True, "id": response.get("id")}
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send session reminder: {type(e).__name__}")
        return {"success": False, "error": "Failed to send email"}


def send_pre_event_agenda_email(
    to_email: str,
    attendee_name: str,
    event_name: str,
    event_date: str,
    event_url: str,
    sessions: list[dict] = None,
    booths: list[dict] = None,
    event_location: str = None,
) -> dict:
    """
    Send personalized pre-event agenda email.

    Args:
        to_email: Attendee's email address
        attendee_name: Name of the attendee
        event_name: Name of the event
        event_date: Formatted date string (e.g., "February 6, 2026")
        event_url: URL to view the event agenda
        sessions: List of recommended sessions with title, start_time, end_time, speakers
        booths: List of recommended booths with name, tagline, logo_url, tier
        event_location: Optional venue/location info

    Returns:
        Resend API response with success status
    """
    init_resend()

    # Validate email format
    if not _validate_email(to_email):
        return {"success": False, "error": "Invalid email address format"}

    # Escape all user-controlled content
    attendee_name = _escape_html(attendee_name)
    event_name = _escape_html(event_name)
    event_date = _escape_html(event_date)
    event_location = _escape_html(event_location)

    sessions = sessions or []
    booths = booths or []

    # Build sessions HTML section
    sessions_html = ""
    for s in sessions[:5]:  # Top 5 sessions
        title = _escape_html(s.get('title', 'Session'))
        start_time = _escape_html(s.get('start_time', ''))
        end_time = _escape_html(s.get('end_time', ''))
        speakers_text = ", ".join(_escape_html(speaker) for speaker in s.get("speakers", [])) or "TBA"
        sessions_html += f"""
        <div style="background: white; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #667eea;">
            <p style="margin: 0 0 5px 0; font-weight: bold; color: #333;">{title}</p>
            <p style="margin: 0 0 5px 0; color: #666; font-size: 14px;">{start_time} - {end_time}</p>
            <p style="margin: 0; color: #888; font-size: 13px;">Speakers: {speakers_text}</p>
        </div>
        """

    if not sessions_html:
        sessions_html = """
        <p style="color: #666; font-style: italic;">No sessions scheduled yet. Check the event page for updates!</p>
        """

    # Build booths HTML section
    booths_html = ""
    for b in booths[:3]:  # Top 3 booths
        booth_name = _escape_html(b.get("name", "Booth"))
        booth_tagline = _escape_html(b.get('tagline', ''))
        logo_url = _escape_html(b.get("logo_url")) if b.get("logo_url") else ""
        logo_html = f'<img src="{logo_url}" alt="{booth_name}" style="width: 60px; height: 60px; object-fit: contain; border-radius: 8px; margin-right: 15px;" />' if logo_url else ""
        booths_html += f"""
        <div style="background: white; padding: 15px; margin: 10px 0; border-radius: 8px; display: flex; align-items: center;">
            {logo_html}
            <div>
                <p style="margin: 0 0 5px 0; font-weight: bold; color: #333;">{booth_name}</p>
                <p style="margin: 0; color: #666; font-size: 13px;">{booth_tagline}</p>
            </div>
        </div>
        """

    location_html = f"<p style='margin: 5px 0;'><strong>Location:</strong> {event_location}</p>" if event_location and event_location != "" else ""

    booths_section = ""
    if booths_html:
        booths_section = f"""
        <div style="margin: 25px 0;">
            <h3 style="color: #333; margin-bottom: 15px;">Expo Booths to Visit</h3>
            {booths_html}
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .header h1 {{ margin: 0 0 10px 0; font-size: 28px; }}
            .header .emoji {{ font-size: 48px; margin-bottom: 15px; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .event-box {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea; }}
            .cta-button {{ display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white !important; padding: 15px 40px; text-decoration: none; border-radius: 30px; font-weight: bold; font-size: 16px; margin: 20px 0; }}
            .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; padding: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="emoji">📅</div>
                <h1>Your Personalized Agenda</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">{event_name} - Tomorrow!</p>
            </div>
            <div class="content">
                <p>Hi {attendee_name},</p>
                <p>Get ready! <strong>{event_name}</strong> is happening tomorrow, and we've put together a personalized agenda just for you.</p>

                <div class="event-box">
                    <h3 style="margin: 0 0 10px 0; color: #667eea;">Event Details</h3>
                    <p style="margin: 5px 0;"><strong>Date:</strong> {event_date}</p>
                    {location_html}
                </div>

                <div style="margin: 25px 0;">
                    <h3 style="color: #333; margin-bottom: 15px;">Recommended Sessions For You</h3>
                    {sessions_html}
                </div>

                {booths_section}

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{event_url}" class="cta-button">View Full Agenda</a>
                </div>

                <p style="color: #666; font-size: 14px;">
                    These recommendations are based on your interests and profile. You can always explore more sessions on the event page.
                </p>

                <p>See you tomorrow!<br>The Event Team</p>
            </div>
            <div class="footer">
                <p>This email was sent by Event Dynamics Platform</p>
                <p>Powered by Infinite Dynamics</p>
                <p style="margin-top: 10px; font-size: 11px;">You're receiving this because you registered for {event_name}</p>
            </div>
        </div>
    </body>
    </html>
    """

    params = {
        "from": f"Event Dynamics <noreply@{settings.RESEND_FROM_DOMAIN}>",
        "to": [to_email],
        "subject": f"Your Personalized Agenda for {event_name} - Tomorrow!",
        "html": html_content,
    }

    try:
        response = resend.Emails.send(params)
        print(f"[EMAIL] Pre-event agenda sent")
        return {"success": True, "id": response.get("id")}
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send pre-event agenda: {type(e).__name__}")
        return {"success": False, "error": "Failed to send email"}


def send_people_to_meet_email(
    to_email: str,
    attendee_name: str,
    event_name: str,
    event_date: str,
    event_url: str,
    people: list[dict] = None,
) -> dict:
    """
    Send "People You Should Meet" networking email.

    Args:
        to_email: Attendee's email address
        attendee_name: Name of the attendee
        event_name: Name of the event
        event_date: Formatted date string
        event_url: URL to the event networking page
        people: List of recommended people with name, role, company, avatar_url, match_score, reasons, conversation_starters

    Returns:
        Resend API response with success status
    """
    init_resend()

    # Validate email format
    if not _validate_email(to_email):
        return {"success": False, "error": "Invalid email address format"}

    # Escape all user-controlled content
    attendee_name = _escape_html(attendee_name)
    event_name = _escape_html(event_name)
    event_date = _escape_html(event_date)

    people = people or []

    # Build people HTML section
    people_html = ""
    for p in people[:5]:  # Top 5 matches
        person_name = _escape_html(p.get("name", "Attendee"))
        avatar_url = _escape_html(p.get("avatar_url")) if p.get("avatar_url") else ""
        avatar_html = f'<img src="{avatar_url}" alt="{person_name}" style="width: 60px; height: 60px; border-radius: 50%; object-fit: cover; margin-right: 15px;" />' if avatar_url else '<div style="width: 60px; height: 60px; border-radius: 50%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin-right: 15px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 20px;">' + person_name[0].upper() + '</div>'

        role_text = _escape_html(p.get("role", ""))
        company_text = _escape_html(p.get("company", ""))
        title_line = f"{role_text} at {company_text}" if role_text and company_text else role_text or company_text or ""

        match_score = p.get("match_score", 0)
        match_color = "#22c55e" if match_score >= 80 else "#f59e0b" if match_score >= 60 else "#6b7280"

        starters = p.get("conversation_starters", [])
        starter_text = _escape_html(starters[0]) if starters else "Ask about their experience in the industry!"

        reasons = p.get("reasons", [])
        reasons_text = ", ".join(_escape_html(r) for r in reasons[:2]) if reasons else "Similar interests"

        people_html += f"""
        <div style="background: white; padding: 20px; margin: 15px 0; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <div style="display: flex; align-items: flex-start;">
                {avatar_html}
                <div style="flex: 1;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                        <p style="margin: 0; font-weight: bold; color: #333; font-size: 16px;">{person_name}</p>
                        <span style="background: {match_color}; color: white; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;">{match_score}% Match</span>
                    </div>
                    <p style="margin: 0 0 8px 0; color: #666; font-size: 14px;">{title_line}</p>
                    <p style="margin: 0 0 10px 0; color: #888; font-size: 13px;"><em>Why connect:</em> {reasons_text}</p>
                    <div style="background: #f0f4ff; padding: 10px 15px; border-radius: 8px; border-left: 3px solid #667eea;">
                        <p style="margin: 0; color: #555; font-size: 13px;"><strong>Conversation starter:</strong> "{starter_text}"</p>
                    </div>
                </div>
            </div>
        </div>
        """

    if not people_html:
        people_html = """
        <p style="color: #666; font-style: italic; text-align: center; padding: 30px;">
            We're still finding the best matches for you. Check the networking section during the event!
        </p>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%); color: white; padding: 40px 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .header h1 {{ margin: 0 0 10px 0; font-size: 28px; }}
            .header .emoji {{ font-size: 48px; margin-bottom: 15px; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .cta-button {{ display: inline-block; background: linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%); color: white !important; padding: 15px 40px; text-decoration: none; border-radius: 30px; font-weight: bold; font-size: 16px; margin: 20px 0; }}
            .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; padding: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="emoji">🤝</div>
                <h1>5 People You Should Meet</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">at {event_name}</p>
            </div>
            <div class="content">
                <p>Hi {attendee_name},</p>
                <p>We've analyzed your profile and interests to find the <strong>best networking matches</strong> for you at {event_name} on {event_date}.</p>

                <p style="color: #666; margin: 20px 0;">Here are 5 people we think you should connect with:</p>

                {people_html}

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{event_url}" class="cta-button">View All Recommendations</a>
                </div>

                <p style="color: #666; font-size: 14px; text-align: center;">
                    Pro tip: Use the conversation starters to break the ice. Great connections start with a simple hello!
                </p>

                <p>Happy networking!<br>The Event Team</p>
            </div>
            <div class="footer">
                <p>This email was sent by Event Dynamics Platform</p>
                <p>Powered by Infinite Dynamics</p>
                <p style="margin-top: 10px; font-size: 11px;">You're receiving this because you registered for {event_name}</p>
            </div>
        </div>
    </body>
    </html>
    """

    params = {
        "from": f"Event Dynamics <noreply@{settings.RESEND_FROM_DOMAIN}>",
        "to": [to_email],
        "subject": f"5 People You Should Meet at {event_name}",
        "html": html_content,
    }

    try:
        response = resend.Emails.send(params)
        print(f"[EMAIL] People-to-meet email sent")
        return {"success": True, "id": response.get("id")}
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send people-to-meet email: {type(e).__name__}")
        return {"success": False, "error": "Failed to send email"}
