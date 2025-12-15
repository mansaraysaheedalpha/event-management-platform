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
                <p>This email was sent by GlobalConnect Event Platform</p>
                <p>Powered by Infinite Dynamics</p>
            </div>
        </div>
    </body>
    </html>
    """

    params = {
        "from": f"GlobalConnect <noreply@{settings.RESEND_FROM_DOMAIN}>",
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
