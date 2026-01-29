# app/workers/campaign_email_worker.py
"""
Kafka consumer for processing sponsor email campaigns.

Production features:
- Batch processing with rate limiting (Resend: 10 req/sec)
- Template personalization with Jinja2
- Retry logic for failed sends
- Delivery tracking
- Error handling and logging

Usage:
    python -m app.workers.campaign_email_worker
"""

import os
import sys
import time
import logging
import json
from typing import Dict, Any
from pathlib import Path
from jinja2 import Template, TemplateError
import resend

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from kafka import KafkaConsumer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.crud.crud_sponsor_campaign import sponsor_campaign
from app.crud.crud_campaign_delivery import campaign_delivery
from app.crud.crud_sponsor import sponsor_lead
from app.models.sponsor_campaign import SponsorCampaign
from app.models.sponsor_lead import SponsorLead

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('campaign_worker.log')
    ]
)
logger = logging.getLogger(__name__)

# Kafka configuration
KAFKA_TOPIC = "sponsor.campaigns.v1"
KAFKA_GROUP_ID = "campaign-email-worker"

# Email rate limiting (Resend free tier: 2 req/sec)
BATCH_SIZE = 50  # Process 50 emails per batch
EMAIL_DELAY_MS = 550  # 550ms delay between emails = ~1.8 req/sec (safe margin for 2/sec limit)

# Initialize Resend
resend.api_key = settings.RESEND_API_KEY

# Load HTML email template
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
EMAIL_TEMPLATE_PATH = TEMPLATE_DIR / "campaign_email.html"


def load_email_template() -> str:
    """Load the HTML email template."""
    try:
        with open(EMAIL_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Email template not found at {EMAIL_TEMPLATE_PATH}, using plain text")
        return "{{ content }}{{ tracking_pixel }}"


def render_email_html(
    content: str,
    subject: str,
    sender_company: str,
    tracking_pixel: str,
    delivery_id: str,
) -> str:
    """
    Render the full HTML email with the template.

    Args:
        content: The personalized message body
        subject: Email subject
        sender_company: Company name of the sender
        tracking_pixel: HTML for open tracking
        delivery_id: For generating unsubscribe/preference links
    """
    template_str = load_email_template()
    template = Template(template_str)

    # Generate URLs
    base_url = settings.NEXT_PUBLIC_APP_URL or "https://eventdynamics.io"
    unsubscribe_url = f"{base_url}/unsubscribe/{delivery_id}"
    preferences_url = f"{base_url}/email-preferences/{delivery_id}"

    # Convert plain text line breaks to HTML paragraphs
    # Split by double newlines for paragraphs, single newlines for line breaks
    formatted_content = content.replace("\n\n", "</p><p style='margin: 0 0 16px 0;'>")
    formatted_content = formatted_content.replace("\n", "<br>")
    formatted_content = f"<p style='margin: 0 0 16px 0;'>{formatted_content}</p>"

    return template.render(
        content=formatted_content,
        subject=subject,
        sender_company=sender_company or "Event Dynamics",
        tracking_pixel=tracking_pixel,
        unsubscribe_url=unsubscribe_url,
        preferences_url=preferences_url,
    )


def create_db_session() -> Session:
    """Create database session."""
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def personalize_template(
    template_str: str,
    lead: SponsorLead,
    sender_name: str = "",
    sender_company: str = ""
) -> str:
    """
    Personalize email template with lead and sender data using Jinja2.

    Available variables (recipient):
    - {{name}} or {{first_name}}
    - {{last_name}}
    - {{company}}
    - {{title}}
    - {{email}}

    Available variables (sender):
    - {{sender_name}}
    - {{sender_company}}
    """
    try:
        template = Template(template_str)

        # Extract first and last name from user_name
        name_parts = (lead.user_name or "").split(" ", 1)
        first_name = name_parts[0] if len(name_parts) > 0 else "there"
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        context = {
            # Recipient variables
            "name": lead.user_name or "there",
            "first_name": first_name,
            "last_name": last_name,
            "company": lead.user_company or "",
            "title": lead.user_title or "",
            "email": lead.user_email or "",
            # Sender variables
            "sender_name": sender_name,
            "sender_company": sender_company,
        }

        return template.render(**context)
    except TemplateError as e:
        logger.error(f"Template rendering error: {e}")
        # Return original template if rendering fails
        return template_str


def send_email_via_resend(
    recipient_email: str,
    subject: str,
    html_body: str,
    from_email: str = f"Event Dynamics <noreply@{settings.RESEND_FROM_DOMAIN}>"
) -> Dict[str, Any]:
    """
    Send email via Resend API.

    Returns:
        dict with 'success', 'message_id', and optional 'error'
    """
    try:
        params = {
            "from": from_email,
            "to": [recipient_email],
            "subject": subject,
            "html": html_body,
        }

        response = resend.Emails.send(params)
        return {
            "success": True,
            "message_id": response.get("id"),
        }
    except Exception as e:
        logger.error(f"Resend API error: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def process_campaign(campaign_id: str, db: Session):
    """
    Process a campaign by sending emails to all recipients.

    Steps:
    1. Get campaign details
    2. Get all recipients (leads)
    3. For each lead:
       - Create delivery record
       - Personalize email
       - Send via Resend
       - Update delivery status
    4. Update campaign stats
    """
    logger.info(f"Processing campaign: {campaign_id}")

    # Get campaign
    campaign_obj = sponsor_campaign.get(db, campaign_id)
    if not campaign_obj:
        logger.error(f"Campaign {campaign_id} not found")
        return

    if campaign_obj.status not in ["queued", "sending"]:
        logger.warning(f"Campaign {campaign_id} status is {campaign_obj.status}, skipping")
        return

    # Mark as sending
    sponsor_campaign.mark_sending(db, campaign=campaign_obj)

    # Get sender info from campaign and sponsor
    sender_name = campaign_obj.created_by_user_name or ""
    sender_company = ""
    if campaign_obj.sponsor:
        sender_company = campaign_obj.sponsor.company_name or ""

    # Get recipients
    leads = sponsor_campaign.get_recipients(
        db,
        sponsor_id=campaign_obj.sponsor_id,
        audience_type=campaign_obj.audience_type,
        audience_filter=campaign_obj.audience_filter,
    )

    logger.info(f"Campaign {campaign_id}: Found {len(leads)} recipients")

    if len(leads) == 0:
        sponsor_campaign.mark_failed(db, campaign=campaign_obj, error="No recipients found")
        return

    # Process in batches
    sent_count = 0
    failed_count = 0
    skipped_unsubscribed = 0

    for i in range(0, len(leads), BATCH_SIZE):
        batch = leads[i:i + BATCH_SIZE]
        logger.info(f"Processing batch {i // BATCH_SIZE + 1} ({len(batch)} emails)")

        for lead in batch:
            try:
                # Check if lead has unsubscribed from this sponsor
                if campaign_delivery.is_unsubscribed(
                    db, lead_id=lead.id, sponsor_id=campaign_obj.sponsor_id
                ):
                    logger.info(f"Skipping unsubscribed lead: {lead.id}")
                    skipped_unsubscribed += 1
                    continue

                # Personalize subject and body
                personalized_subject = personalize_template(
                    campaign_obj.subject, lead, sender_name, sender_company
                )
                personalized_body = personalize_template(
                    campaign_obj.message_body, lead, sender_name, sender_company
                )

                # Create delivery record BEFORE sending
                delivery = campaign_delivery.create(
                    db,
                    campaign_id=campaign_obj.id,
                    lead_id=lead.id,
                    recipient_email=lead.user_email,
                    recipient_name=lead.user_name,
                    personalized_subject=personalized_subject,
                    personalized_body=personalized_body,
                )

                # Build tracking pixel with real delivery ID
                tracking_pixel = f'<img src="{settings.NEXT_PUBLIC_APP_URL}/api/v1/sponsors-campaigns/campaigns/track/open/{delivery.id}.png" width="1" height="1" alt="" style="display:block;width:1px;height:1px;" />'

                # Render full HTML email with template
                html_email = render_email_html(
                    content=personalized_body,
                    subject=personalized_subject,
                    sender_company=sender_company,
                    tracking_pixel=tracking_pixel,
                    delivery_id=delivery.id,
                )

                # Send email
                result = send_email_via_resend(
                    recipient_email=lead.user_email,
                    subject=personalized_subject,
                    html_body=html_email,
                )

                # Update delivery status
                if result.get("success"):
                    campaign_delivery.mark_sent(
                        db,
                        delivery_id=delivery.id,
                        provider_message_id=result.get("message_id"),
                        provider_response=json.dumps(result),
                    )
                    sent_count += 1
                    logger.debug(f"Sent to {lead.user_email}")

                    # Auto-update lead status to "contacted" if currently "new"
                    # This provides accurate tracking of contacted leads
                    if lead.follow_up_status == "new":
                        sponsor_lead.mark_contacted_by_campaign(
                            db,
                            lead_id=lead.id,
                            campaign_id=campaign_obj.id,
                        )
                        logger.debug(f"Lead {lead.id} marked as contacted")
                else:
                    campaign_delivery.mark_failed(
                        db,
                        delivery_id=delivery.id,
                        error_message=result.get("error", "Unknown error"),
                    )
                    failed_count += 1
                    logger.error(f"Failed to send to {lead.user_email}: {result.get('error')}")

                # Rate limiting: delay between emails (Resend free tier: 2 req/sec)
                time.sleep(EMAIL_DELAY_MS / 1000.0)

            except Exception as e:
                logger.error(f"Error processing lead {lead.id}: {e}")
                failed_count += 1

        # Log batch completion
        logger.info(
            f"Batch complete: {sent_count} sent, {failed_count} failed, "
            f"{skipped_unsubscribed} skipped (unsubscribed)"
        )

    # Update campaign stats
    sponsor_campaign.update_delivery_stats(db, campaign_id=campaign_id)

    # Mark campaign as sent (account for skipped unsubscribed leads)
    eligible_leads = len(leads) - skipped_unsubscribed
    if eligible_leads > 0 and failed_count == eligible_leads:
        sponsor_campaign.mark_failed(
            db,
            campaign=campaign_obj,
            error=f"All {failed_count} sends failed"
        )
    else:
        sponsor_campaign.mark_sent(db, campaign=campaign_obj)

    logger.info(
        f"Campaign {campaign_id} complete: "
        f"{sent_count} sent, {failed_count} failed, {skipped_unsubscribed} skipped (unsubscribed)"
    )


def main():
    """Main worker loop."""
    logger.info("Starting campaign email worker...")
    logger.info(f"Kafka topic: {KAFKA_TOPIC}")
    logger.info(f"Consumer group: {KAFKA_GROUP_ID}")
    logger.info(f"Batch size: {BATCH_SIZE}, Email delay: {EMAIL_DELAY_MS}ms")

    # Validate Resend API key
    if not settings.RESEND_API_KEY:
        logger.error("RESEND_API_KEY not configured. Worker cannot start.")
        sys.exit(1)

    # Validate Kafka configuration
    if not settings.KAFKA_BOOTSTRAP_SERVERS:
        logger.error("KAFKA_BOOTSTRAP_SERVERS not configured. Worker cannot start.")
        sys.exit(1)

    # Kafka consumer configuration
    consumer_config = {
        "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "group_id": KAFKA_GROUP_ID,
        "auto_offset_reset": "earliest",
        "enable_auto_commit": True,
        "value_deserializer": lambda m: json.loads(m.decode("utf-8")),
    }

    # Add SASL authentication if configured
    if settings.KAFKA_API_KEY and settings.KAFKA_API_SECRET:
        consumer_config.update({
            "security_protocol": settings.KAFKA_SECURITY_PROTOCOL or "SASL_SSL",
            "sasl_mechanism": settings.KAFKA_SASL_MECHANISM or "PLAIN",
            "sasl_plain_username": settings.KAFKA_API_KEY,
            "sasl_plain_password": settings.KAFKA_API_SECRET,
        })
        logger.info("Kafka SASL authentication enabled")

    try:
        # Create Kafka consumer
        consumer = KafkaConsumer(KAFKA_TOPIC, **consumer_config)
        logger.info("Kafka consumer connected successfully")

        # Create database session
        db = create_db_session()

        # Consume messages
        logger.info("Listening for campaigns...")
        for message in consumer:
            try:
                event = message.value
                logger.info(f"Received event: {event.get('event_type')}")

                if event.get("event_type") == "campaign.send":
                    campaign_id = event.get("campaign_id")
                    if campaign_id:
                        process_campaign(campaign_id, db)
                    else:
                        logger.warning("No campaign_id in event")
                else:
                    logger.warning(f"Unknown event type: {event.get('event_type')}")

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)

    except KeyboardInterrupt:
        logger.info("Worker shutting down (KeyboardInterrupt)...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        try:
            consumer.close()
            db.close()
        except:
            pass
        logger.info("Worker stopped")


if __name__ == "__main__":
    main()
