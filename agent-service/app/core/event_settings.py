"""
Event Agent Settings Loader

Provides efficient loading and caching of per-event agent settings.
Integrates with engagement_conductor, thompson_sampling, and rate_limiter.
"""
import logging
from typing import Dict, Optional, List, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from sqlalchemy import select

from app.db.timescale import AsyncSessionLocal
from app.models.event_agent_settings import EventAgentSettings

logger = logging.getLogger(__name__)


@dataclass
class CachedEventSettings:
    """Cached event settings with TTL"""
    event_id: str
    agent_enabled: bool
    agent_mode: str
    auto_approve_threshold: float
    min_confidence_threshold: float
    allowed_interventions: Optional[Set[str]]
    max_interventions_per_hour: int
    notify_on_anomaly: bool
    notify_on_intervention: bool
    notification_emails: Optional[List[str]]
    cached_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_expired(self, ttl_seconds: int = 60) -> bool:
        """Check if cache entry has expired"""
        age = (datetime.now(timezone.utc) - self.cached_at).total_seconds()
        return age > ttl_seconds

    def is_intervention_allowed(self, intervention_type: str) -> bool:
        """Check if intervention type is in the allowed list"""
        if self.allowed_interventions is None:
            return True  # No whitelist means all allowed
        return intervention_type in self.allowed_interventions


# Default settings when no per-event config exists
DEFAULT_SETTINGS = CachedEventSettings(
    event_id="__default__",
    agent_enabled=True,
    agent_mode="SEMI_AUTO",
    auto_approve_threshold=0.75,
    min_confidence_threshold=0.50,
    allowed_interventions=None,  # All allowed
    max_interventions_per_hour=10,  # Reasonable default
    notify_on_anomaly=True,
    notify_on_intervention=True,
    notification_emails=None,
)


class EventSettingsLoader:
    """
    Loads and caches per-event agent settings.

    Uses in-memory cache with TTL to minimize database queries.
    Falls back to sensible defaults if settings not found.
    """

    # Cache TTL in seconds (1 minute)
    CACHE_TTL_SECONDS = 60

    def __init__(self):
        self._cache: Dict[str, CachedEventSettings] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    async def get_settings(self, event_id: str) -> CachedEventSettings:
        """
        Get settings for an event, using cache when available.

        Args:
            event_id: Event ID to get settings for

        Returns:
            CachedEventSettings with event-specific or default values
        """
        # Check cache
        if event_id in self._cache:
            cached = self._cache[event_id]
            if not cached.is_expired(self.CACHE_TTL_SECONDS):
                self._cache_hits += 1
                return cached

        # Cache miss - load from database
        self._cache_misses += 1
        settings = await self._load_from_db(event_id)
        self._cache[event_id] = settings

        return settings

    async def _load_from_db(self, event_id: str) -> CachedEventSettings:
        """Load settings from database"""
        try:
            if AsyncSessionLocal is None:
                logger.debug(f"Database not configured, using defaults for event {event_id}")
                return self._create_default_settings(event_id)

            async with AsyncSessionLocal() as db:
                stmt = select(EventAgentSettings).where(
                    EventAgentSettings.event_id == event_id
                )
                result = await db.execute(stmt)
                db_settings = result.scalar_one_or_none()

                if db_settings is None:
                    logger.debug(f"No settings found for event {event_id}, using defaults")
                    return self._create_default_settings(event_id)

                # Convert to cached settings
                allowed_set = None
                if db_settings.allowed_interventions:
                    allowed_set = set(db_settings.allowed_interventions)

                return CachedEventSettings(
                    event_id=event_id,
                    agent_enabled=db_settings.agent_enabled,
                    agent_mode=db_settings.agent_mode,
                    auto_approve_threshold=db_settings.auto_approve_threshold,
                    min_confidence_threshold=db_settings.min_confidence_threshold,
                    allowed_interventions=allowed_set,
                    max_interventions_per_hour=db_settings.max_interventions_per_hour,
                    notify_on_anomaly=db_settings.notify_on_anomaly,
                    notify_on_intervention=db_settings.notify_on_intervention,
                    notification_emails=db_settings.notification_emails,
                )

        except Exception as e:
            logger.warning(f"Error loading settings for event {event_id}: {e}. Using defaults.")
            return self._create_default_settings(event_id)

    def _create_default_settings(self, event_id: str) -> CachedEventSettings:
        """Create default settings for an event"""
        return CachedEventSettings(
            event_id=event_id,
            agent_enabled=DEFAULT_SETTINGS.agent_enabled,
            agent_mode=DEFAULT_SETTINGS.agent_mode,
            auto_approve_threshold=DEFAULT_SETTINGS.auto_approve_threshold,
            min_confidence_threshold=DEFAULT_SETTINGS.min_confidence_threshold,
            allowed_interventions=DEFAULT_SETTINGS.allowed_interventions,
            max_interventions_per_hour=DEFAULT_SETTINGS.max_interventions_per_hour,
            notify_on_anomaly=DEFAULT_SETTINGS.notify_on_anomaly,
            notify_on_intervention=DEFAULT_SETTINGS.notify_on_intervention,
            notification_emails=DEFAULT_SETTINGS.notification_emails,
        )

    def invalidate(self, event_id: str):
        """Invalidate cache for a specific event (call after settings update)"""
        if event_id in self._cache:
            del self._cache[event_id]
            logger.debug(f"Invalidated settings cache for event {event_id}")

    def invalidate_all(self):
        """Invalidate entire cache"""
        self._cache.clear()
        logger.debug("Invalidated all settings cache")

    @property
    def stats(self) -> Dict:
        """Get cache statistics"""
        total = self._cache_hits + self._cache_misses
        return {
            "cache_size": len(self._cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": self._cache_hits / total if total > 0 else 0.0,
        }


# Global singleton
_settings_loader: Optional[EventSettingsLoader] = None


def get_event_settings_loader() -> EventSettingsLoader:
    """Get or create the global settings loader"""
    global _settings_loader
    if _settings_loader is None:
        _settings_loader = EventSettingsLoader()
    return _settings_loader


async def get_event_settings(event_id: str) -> CachedEventSettings:
    """Convenience function to get settings for an event"""
    loader = get_event_settings_loader()
    return await loader.get_settings(event_id)


# ==================== NOTIFICATION SERVICE ====================

class NotificationService:
    """
    Notification service for sending real-time alerts to organizers.

    Supports:
    - Email notifications via Resend
    - In-app notifications via Redis pub/sub (for frontend notification bell)
    """

    def __init__(self):
        self._resend_initialized = False

    def _init_resend(self):
        """Initialize Resend API key if not already done"""
        if self._resend_initialized:
            return True

        try:
            import resend
            from app.core.config import settings

            if not settings.RESEND_API_KEY:
                logger.warning("RESEND_API_KEY not configured - email notifications disabled")
                return False

            resend.api_key = settings.RESEND_API_KEY
            self._resend_initialized = True
            return True
        except ImportError:
            logger.warning("resend package not installed - email notifications disabled")
            return False

    def _get_severity_color(self, severity: str) -> tuple:
        """Get color scheme based on severity"""
        colors = {
            "CRITICAL": ("#dc3545", "#fff5f5", "Critical"),
            "WARNING": ("#ffc107", "#fff8e6", "Warning"),
            "INFO": ("#17a2b8", "#e8f7fa", "Info"),
        }
        return colors.get(severity.upper(), ("#6c757d", "#f8f9fa", "Unknown"))

    async def notify_anomaly_detected(
        self,
        event_id: str,
        session_id: str,
        anomaly_type: str,
        severity: str,
        engagement_score: float,
        settings: CachedEventSettings
    ):
        """
        Send notification when an anomaly is detected.

        Only sends if settings.notify_on_anomaly is True.
        Uses settings.notification_emails for recipients.
        """
        if not settings.notify_on_anomaly:
            return

        if not settings.notification_emails:
            logger.debug(f"No notification emails configured for event {event_id}")
            return

        # Send email notification
        await self._send_anomaly_email(
            event_id=event_id,
            session_id=session_id,
            anomaly_type=anomaly_type,
            severity=severity,
            engagement_score=engagement_score,
            emails=settings.notification_emails,
        )

        # Publish to Redis for in-app notification bell
        await self._publish_in_app_notification(
            event_id=event_id,
            notification_type="anomaly_detected",
            data={
                "session_id": session_id,
                "anomaly_type": anomaly_type,
                "severity": severity,
                "engagement_score": engagement_score,
            }
        )

    async def _send_anomaly_email(
        self,
        event_id: str,
        session_id: str,
        anomaly_type: str,
        severity: str,
        engagement_score: float,
        emails: List[str],
    ):
        """Send anomaly detection email via Resend"""
        if not self._init_resend():
            return

        import resend
        from app.core.config import settings

        color, bg_color, severity_label = self._get_severity_color(severity)
        dashboard_url = f"{settings.FRONTEND_URL}/organizer/events/{event_id}/sessions/{session_id}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: {color}; color: white; padding: 25px 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .alert-box {{ background: {bg_color}; border-left: 4px solid {color}; padding: 20px; margin: 20px 0; border-radius: 4px; }}
                .metric {{ display: inline-block; background: white; padding: 15px 25px; margin: 10px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .metric-value {{ font-size: 28px; font-weight: bold; color: {color}; }}
                .metric-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
                .cta-button {{ display: inline-block; background: {color}; color: white; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; margin-top: 20px; }}
                .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Anomaly Detected</h1>
                    <p style="margin: 5px 0 0 0; opacity: 0.9;">{severity_label} Alert</p>
                </div>
                <div class="content">
                    <div class="alert-box">
                        <p style="margin: 0;"><strong>Type:</strong> {anomaly_type.replace('_', ' ').title()}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Session ID:</strong> {session_id}</p>
                    </div>

                    <div style="text-align: center; margin: 25px 0;">
                        <div class="metric">
                            <div class="metric-value">{engagement_score:.1%}</div>
                            <div class="metric-label">Engagement Score</div>
                        </div>
                    </div>

                    <p>The AI engagement agent has detected unusual patterns in your event session. Review the dashboard for details and take action if needed.</p>

                    <div style="text-align: center;">
                        <a href="{dashboard_url}" class="cta-button">View Dashboard</a>
                    </div>
                </div>
                <div class="footer">
                    <p>Event Dynamics Platform - AI Engagement Agent</p>
                    <p>You're receiving this because anomaly notifications are enabled for this event.</p>
                </div>
            </div>
        </body>
        </html>
        """

        severity_emoji = {"CRITICAL": "🚨", "WARNING": "⚠️", "INFO": "ℹ️"}.get(severity.upper(), "📊")

        params = {
            "from": f"Event Dynamics <noreply@{settings.RESEND_FROM_DOMAIN}>",
            "to": emails,
            "subject": f"{severity_emoji} {severity_label} Alert: {anomaly_type.replace('_', ' ').title()} detected",
            "html": html_content,
        }

        try:
            response = resend.Emails.send(params)
            logger.info(f"Anomaly notification sent to {emails} for event {event_id}")
            return {"success": True, "id": response.get("id")}
        except Exception as e:
            logger.error(f"Failed to send anomaly email to {emails}: {e}")
            return {"success": False, "error": str(e)}

    async def notify_intervention_executed(
        self,
        event_id: str,
        session_id: str,
        intervention_type: str,
        confidence: float,
        auto_approved: bool,
        settings: CachedEventSettings
    ):
        """
        Send notification when an intervention is executed.

        Only sends if settings.notify_on_intervention is True.
        Uses settings.notification_emails for recipients.
        """
        if not settings.notify_on_intervention:
            return

        if not settings.notification_emails:
            logger.debug(f"No notification emails configured for event {event_id}")
            return

        approval_method = "auto-approved" if auto_approved else "manually approved"

        # Send email notification
        await self._send_intervention_email(
            event_id=event_id,
            session_id=session_id,
            intervention_type=intervention_type,
            confidence=confidence,
            approval_method=approval_method,
            emails=settings.notification_emails,
        )

        # Publish to Redis for in-app notification bell
        await self._publish_in_app_notification(
            event_id=event_id,
            notification_type="intervention_executed",
            data={
                "session_id": session_id,
                "intervention_type": intervention_type,
                "confidence": confidence,
                "auto_approved": auto_approved,
            }
        )

    async def _send_intervention_email(
        self,
        event_id: str,
        session_id: str,
        intervention_type: str,
        confidence: float,
        approval_method: str,
        emails: List[str],
    ):
        """Send intervention execution email via Resend"""
        if not self._init_resend():
            return

        import resend
        from app.core.config import settings

        dashboard_url = f"{settings.FRONTEND_URL}/organizer/events/{event_id}/sessions/{session_id}"

        # Color based on confidence
        if confidence >= 0.8:
            conf_color = "#28a745"  # green
        elif confidence >= 0.6:
            conf_color = "#ffc107"  # yellow
        else:
            conf_color = "#dc3545"  # red

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .info-box {{ background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .metric {{ display: inline-block; background: white; padding: 15px 25px; margin: 10px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .metric-value {{ font-size: 28px; font-weight: bold; color: {conf_color}; }}
                .metric-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
                .badge {{ display: inline-block; padding: 5px 12px; border-radius: 15px; font-size: 12px; font-weight: bold; }}
                .badge-auto {{ background: #d4edda; color: #155724; }}
                .badge-manual {{ background: #fff3cd; color: #856404; }}
                .cta-button {{ display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; margin-top: 20px; }}
                .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Intervention Executed</h1>
                    <p style="margin: 5px 0 0 0; opacity: 0.9;">{intervention_type.replace('_', ' ').title()}</p>
                </div>
                <div class="content">
                    <div class="info-box">
                        <p style="margin: 0 0 15px 0;"><strong>Session ID:</strong> {session_id}</p>
                        <p style="margin: 0;">
                            <strong>Approval:</strong>
                            <span class="badge {'badge-auto' if 'auto' in approval_method else 'badge-manual'}">
                                {approval_method.title()}
                            </span>
                        </p>
                    </div>

                    <div style="text-align: center; margin: 25px 0;">
                        <div class="metric">
                            <div class="metric-value">{confidence:.1%}</div>
                            <div class="metric-label">AI Confidence</div>
                        </div>
                    </div>

                    <p>The AI engagement agent has executed an intervention to boost engagement in your session. Monitor the results in your dashboard.</p>

                    <div style="text-align: center;">
                        <a href="{dashboard_url}" class="cta-button">View Dashboard</a>
                    </div>
                </div>
                <div class="footer">
                    <p>Event Dynamics Platform - AI Engagement Agent</p>
                    <p>You're receiving this because intervention notifications are enabled for this event.</p>
                </div>
            </div>
        </body>
        </html>
        """

        params = {
            "from": f"Event Dynamics <noreply@{settings.RESEND_FROM_DOMAIN}>",
            "to": emails,
            "subject": f"🤖 Intervention Executed: {intervention_type.replace('_', ' ').title()}",
            "html": html_content,
        }

        try:
            response = resend.Emails.send(params)
            logger.info(f"Intervention notification sent to {emails} for event {event_id}")
            return {"success": True, "id": response.get("id")}
        except Exception as e:
            logger.error(f"Failed to send intervention email to {emails}: {e}")
            return {"success": False, "error": str(e)}

    async def _publish_in_app_notification(
        self,
        event_id: str,
        notification_type: str,
        data: dict,
    ):
        """
        Publish notification to Redis for in-app notification bell.

        Frontend subscribes to these channels to show real-time notifications.
        Channel pattern: agent:notifications:{event_id}
        """
        try:
            from app.core.redis_client import redis_client
            import json

            if redis_client is None:
                logger.warning("Redis client not initialized, skipping in-app notification")
                return

            notification = {
                "type": notification_type,
                "event_id": event_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **data,
            }

            channel = f"agent:notifications:{event_id}"
            await redis_client.publish(channel, json.dumps(notification))
            logger.debug(f"Published in-app notification to {channel}")
        except Exception as e:
            logger.warning(f"Failed to publish in-app notification: {e}")


# Global notification service instance
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get or create the global notification service"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
