# app/tasks/enrichment_tasks.py
"""
Celery tasks for profile enrichment.

Handles background processing of profile enrichment with:
- Rate limiting (100/hour max)
- Automatic retries with backoff
- Event-based batch processing
- Kafka event publishing for service integration
"""

import asyncio
import logging
from datetime import timedelta
from typing import Any

from celery import shared_task

from app.agents.profile_enrichment import EnrichmentInput, EnrichmentStatus, run_enrichment
from app.agents.profile_enrichment.fallback import EnrichmentFallbackHandler
from app.core.audit import audit_logger
from app.core.config import settings
from app.integrations.kafka_publisher import get_kafka_publisher

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run async coroutine in sync context (for Celery)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(
    bind=True,
    name="app.tasks.enrichment_tasks.enrich_user_task",
    rate_limit=f"{settings.ENRICHMENT_MAX_PER_HOUR}/h",
    retry_backoff=True,
    retry_backoff_max=600,  # Max 10 minute backoff
    max_retries=3,
    autoretry_for=(Exception,),
    retry_jitter=True,
)
def enrich_user_task(
    self,
    user_id: str,
    name: str,
    email: str,
    company: str,
    role: str,
    linkedin_url: str | None = None,
    github_username: str | None = None,
    twitter_handle: str | None = None,
) -> dict[str, Any]:
    """
    Celery task for profile enrichment with built-in rate limiting.

    Args:
        self: Celery task instance (bound)
        user_id: User identifier
        name: User's full name
        email: User's email
        company: User's company
        role: User's job role
        linkedin_url: Optional LinkedIn URL
        github_username: Optional GitHub username
        twitter_handle: Optional Twitter handle

    Returns:
        Dict with enrichment result summary
    """
    logger.info(f"Starting enrichment task for user {user_id} (attempt {self.request.retries + 1})")

    correlation_id = self.request.id
    kafka = get_kafka_publisher()

    try:
        # Publish enrichment started event
        kafka.publish_enrichment_started(
            user_id=user_id,
            correlation_id=correlation_id,
        )

        # Create validated input
        input_data = EnrichmentInput(
            user_id=user_id,
            name=name,
            email=email,
            company=company,
            role=role,
            linkedin_url=linkedin_url,
            github_username=github_username,
            twitter_handle=twitter_handle,
        )

        # Run enrichment agent
        result = run_async(run_enrichment(input_data))

        # Handle result with fallback logic
        fallback_handler = EnrichmentFallbackHandler()
        tier = run_async(fallback_handler.handle_enrichment_result(user_id, result))

        logger.info(
            f"Enrichment completed for {user_id}: "
            f"status={result.status.value}, tier={tier.value}, "
            f"sources={result.sources_found}"
        )

        # Build enriched data matching Prisma UserProfile schema
        enriched_data = {}
        if result.enriched_profile:
            ep = result.enriched_profile
            enriched_data = {
                "enrichmentStatus": result.status.value,
                "enrichedAt": result.processing_time_seconds,
                "linkedInHeadline": ep.linkedin_headline,
                "linkedInUrl": ep.linkedin_url,
                "githubUsername": ep.github_username,
                "githubTopLanguages": ep.github_top_languages,
                "githubRepoCount": ep.github_repo_count,
                "twitterHandle": ep.twitter_handle,
                "twitterBio": ep.twitter_bio,
                "youtubeChannelUrl": ep.youtube_channel_url,
                "youtubeChannelName": ep.youtube_channel_name,
                "youtubeSubscriberRange": ep.youtube_subscriber_range,
                "instagramHandle": ep.instagram_handle,
                "instagramBio": ep.instagram_bio,
                "facebookProfileUrl": ep.facebook_profile_url,
                "extractedSkills": ep.extracted_skills,
                "extractedInterests": ep.extracted_interests,
                "enrichmentSources": ep.sources,
            }

        # Publish enrichment completed event for real-time-service
        kafka.publish_enrichment_completed(
            user_id=user_id,
            profile_tier=tier.value,
            sources_found=result.sources_found,
            enriched_data=enriched_data,
            processing_time_seconds=result.processing_time_seconds,
            correlation_id=correlation_id,
        )

        # Audit log
        audit_logger.log_enrichment_completed(
            user_id=user_id,
            sources_found=result.sources_found,
            profile_tier=tier.value,
            processing_time_seconds=result.processing_time_seconds,
        )

        return {
            "user_id": user_id,
            "status": result.status.value,
            "tier": tier.value,
            "sources_found": result.sources_found,
            "processing_time_seconds": result.processing_time_seconds,
        }

    except Exception as e:
        logger.error(
            f"Enrichment task failed for {user_id} "
            f"(attempt {self.request.retries + 1}): {e}"
        )

        # Publish failure event
        will_retry = self.request.retries < self.max_retries
        kafka.publish_enrichment_failed(
            user_id=user_id,
            error=str(e),
            retry_count=self.request.retries,
            will_retry=will_retry,
            correlation_id=correlation_id,
        )

        # Audit log
        audit_logger.log_enrichment_failed(user_id=user_id, error=str(e))

        raise


@shared_task(
    name="app.tasks.enrichment_tasks.queue_event_enrichments",
    rate_limit="10/m",  # Max 10 event batches per minute
)
def queue_event_enrichments(
    event_id: str,
    attendees: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Queue all attendees for enrichment, spread over time.

    Prevents API spike by staggering enrichment tasks over 6 hours.

    Args:
        event_id: Event identifier
        attendees: List of attendee data dicts with user_id, name, email, etc.

    Returns:
        Summary of queued tasks
    """
    logger.info(f"Queuing enrichments for event {event_id} ({len(attendees)} attendees)")

    queued_count = 0
    skipped_count = 0

    for i, attendee in enumerate(attendees):
        # Skip if already enriched or opted out
        if attendee.get("enrichment_status") in ("COMPLETED", "OPTED_OUT"):
            skipped_count += 1
            continue

        # Calculate delay to spread enrichments over 6 hours
        # Target: ~100 enrichments per hour = ~1.7 per minute = ~36 seconds each
        delay = timedelta(seconds=i * 36)

        # Queue the task with delay
        enrich_user_task.apply_async(
            kwargs={
                "user_id": attendee["user_id"],
                "name": attendee["name"],
                "email": attendee["email"],
                "company": attendee.get("company", ""),
                "role": attendee.get("role", ""),
                "linkedin_url": attendee.get("linkedin_url"),
                "github_username": attendee.get("github_username"),
                "twitter_handle": attendee.get("twitter_handle"),
            },
            countdown=delay.total_seconds(),
            priority=7,  # Lower priority than on-demand enrichments
        )

        queued_count += 1

    logger.info(
        f"Queued {queued_count} enrichments for event {event_id} "
        f"(skipped {skipped_count} already processed)"
    )

    return {
        "event_id": event_id,
        "queued": queued_count,
        "skipped": skipped_count,
        "total": len(attendees),
    }


@shared_task(
    name="app.tasks.enrichment_tasks.retry_failed_enrichments",
    rate_limit="5/m",
)
def retry_failed_enrichments(
    user_ids: list[str],
    user_data: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Retry enrichment for users who previously failed.

    Args:
        user_ids: List of user IDs to retry
        user_data: Dict mapping user_id to their data

    Returns:
        Summary of retried tasks
    """
    logger.info(f"Retrying enrichment for {len(user_ids)} users")

    queued_count = 0

    for i, user_id in enumerate(user_ids):
        data = user_data.get(user_id, {})
        if not data:
            continue

        # Spread retries over time
        delay = timedelta(seconds=i * 60)

        enrich_user_task.apply_async(
            kwargs={
                "user_id": user_id,
                "name": data.get("name", ""),
                "email": data.get("email", ""),
                "company": data.get("company", ""),
                "role": data.get("role", ""),
            },
            countdown=delay.total_seconds(),
            priority=8,  # Lower priority than new enrichments
        )

        queued_count += 1

    return {
        "queued": queued_count,
        "total": len(user_ids),
    }
