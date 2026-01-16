# app/core/email.py
"""
Email service using Resend for sending transactional emails.
"""
import resend
from app.core.config import settings


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

    location_html = f"<p><strong>Location:</strong> {event_location}</p>" if event_location else ""

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
        print(f"[EMAIL] Registration confirmation sent to {to_email} for event: {event_name}")
        return {"success": True, "id": response.get("id")}
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email to {to_email}: {e}")
        return {"success": False, "error": str(e)}


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
        print(f"[EMAIL] Giveaway winner notification sent to {to_email} for event: {event_name}")
        return {"success": True, "id": response.get("id")}
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send giveaway email to {to_email}: {e}")
        return {"success": False, "error": str(e)}


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
        print(f"[EMAIL] Waitlist offer sent to {to_email} for session: {session_title}")
        return {"success": True, "id": response.get("id")}
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send waitlist offer email to {to_email}: {e}")
        return {"success": False, "error": str(e)}
