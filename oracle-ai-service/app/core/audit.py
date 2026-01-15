# app/core/audit.py
"""
Structured audit logging for security-sensitive operations.

Provides:
- Enrichment operation audit trail
- Suspicious activity detection
- Compliance logging for data access
"""

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("audit")


class AuditAction(str, Enum):
    """Audit action types."""

    # Enrichment actions
    ENRICHMENT_REQUESTED = "enrichment.requested"
    ENRICHMENT_STARTED = "enrichment.started"
    ENRICHMENT_COMPLETED = "enrichment.completed"
    ENRICHMENT_FAILED = "enrichment.failed"
    ENRICHMENT_RATE_LIMITED = "enrichment.rate_limited"

    # Data access actions
    PROFILE_ACCESSED = "profile.accessed"
    PROFILE_EXPORTED = "profile.exported"

    # Analytics actions
    ANALYTICS_COMPUTED = "analytics.computed"
    ANALYTICS_EXPORTED = "analytics.exported"

    # Security actions
    SUSPICIOUS_ACTIVITY = "security.suspicious_activity"
    RATE_LIMIT_EXCEEDED = "security.rate_limit_exceeded"


class AuditLogger:
    """
    Structured audit logger for compliance and security.

    All audit logs are written in JSON format for easy parsing
    and analysis by security tools.
    """

    def __init__(self, service_name: str = "oracle-ai-service"):
        self.service_name = service_name

    def log(
        self,
        action: AuditAction,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        success: bool = True,
        error: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Log an audit event.

        Args:
            action: The action being audited
            user_id: User who performed the action
            resource_id: ID of the resource being accessed/modified
            resource_type: Type of resource (user_profile, event, etc.)
            details: Additional context about the action
            success: Whether the action succeeded
            error: Error message if action failed
            ip_address: Client IP address
        """
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": self.service_name,
            "action": action.value,
            "user_id": user_id,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "success": success,
            "error": error,
            "ip_address": ip_address,
            "details": details or {},
        }

        # Log as JSON for structured logging
        logger.info(json.dumps(audit_entry))

    def log_enrichment_request(
        self,
        user_id: str,
        target_user_id: str,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log an enrichment request."""
        self.log(
            action=AuditAction.ENRICHMENT_REQUESTED,
            user_id=user_id,
            resource_id=target_user_id,
            resource_type="user_profile",
            ip_address=ip_address,
        )

    def log_enrichment_completed(
        self,
        user_id: str,
        sources_found: list[str],
        profile_tier: str,
        processing_time_seconds: Optional[float] = None,
    ) -> None:
        """Log a completed enrichment."""
        self.log(
            action=AuditAction.ENRICHMENT_COMPLETED,
            user_id=user_id,
            resource_id=user_id,
            resource_type="user_profile",
            details={
                "sources_found": sources_found,
                "profile_tier": profile_tier,
                "processing_time_seconds": processing_time_seconds,
            },
        )

    def log_enrichment_failed(
        self,
        user_id: str,
        error: str,
    ) -> None:
        """Log a failed enrichment."""
        self.log(
            action=AuditAction.ENRICHMENT_FAILED,
            user_id=user_id,
            resource_id=user_id,
            resource_type="user_profile",
            success=False,
            error=error,
        )

    def log_rate_limit_exceeded(
        self,
        user_id: str,
        limiter_name: str,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log a rate limit violation."""
        self.log(
            action=AuditAction.RATE_LIMIT_EXCEEDED,
            user_id=user_id,
            resource_type="rate_limit",
            ip_address=ip_address,
            success=False,
            details={"limiter": limiter_name},
        )

    def log_suspicious_activity(
        self,
        user_id: str,
        activity_type: str,
        details: dict[str, Any],
        ip_address: Optional[str] = None,
    ) -> None:
        """Log suspicious activity for security review."""
        self.log(
            action=AuditAction.SUSPICIOUS_ACTIVITY,
            user_id=user_id,
            ip_address=ip_address,
            success=False,
            details={
                "activity_type": activity_type,
                **details,
            },
        )

    def log_analytics_export(
        self,
        user_id: str,
        event_id: str,
        export_format: str,
    ) -> None:
        """Log analytics data export."""
        self.log(
            action=AuditAction.ANALYTICS_EXPORTED,
            user_id=user_id,
            resource_id=event_id,
            resource_type="event_analytics",
            details={"format": export_format},
        )


# Global audit logger instance
audit_logger = AuditLogger()
