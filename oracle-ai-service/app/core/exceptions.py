# app/core/exceptions.py
"""
Custom exception hierarchy for the Oracle AI Service.
All exceptions inherit from OracleServiceError for consistent handling.
"""

from typing import Optional


class OracleServiceError(Exception):
    """Base exception for all Oracle service errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "ORACLE_ERROR",
        details: Optional[dict] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


# ===========================================
# Enrichment Exceptions
# ===========================================


class EnrichmentError(OracleServiceError):
    """Base exception for enrichment-related errors."""

    def __init__(self, message: str, user_id: str, **kwargs):
        self.user_id = user_id
        super().__init__(message, error_code="ENRICHMENT_ERROR", **kwargs)


class EnrichmentNotFoundError(EnrichmentError):
    """No enrichment data found for user."""

    def __init__(self, user_id: str):
        super().__init__(
            message=f"No enrichment data found for user {user_id}",
            user_id=user_id,
            details={"user_id": user_id},
        )
        self.error_code = "ENRICHMENT_NOT_FOUND"


class EnrichmentOptedOutError(EnrichmentError):
    """User has opted out of enrichment."""

    def __init__(self, user_id: str):
        super().__init__(
            message=f"User {user_id} has opted out of profile enrichment",
            user_id=user_id,
            details={"user_id": user_id},
        )
        self.error_code = "ENRICHMENT_OPTED_OUT"


class EnrichmentAlreadyProcessingError(EnrichmentError):
    """Enrichment is already in progress for user."""

    def __init__(self, user_id: str):
        super().__init__(
            message=f"Enrichment already in progress for user {user_id}",
            user_id=user_id,
            details={"user_id": user_id},
        )
        self.error_code = "ENRICHMENT_ALREADY_PROCESSING"


class EnrichmentDisabledError(OracleServiceError):
    """Enrichment service is disabled (missing API keys)."""

    def __init__(self):
        super().__init__(
            message="Profile enrichment is disabled. Configure TAVILY_API_KEY and ANTHROPIC_API_KEY.",
            error_code="ENRICHMENT_DISABLED",
        )


# ===========================================
# Rate Limiting Exceptions
# ===========================================


class RateLimitError(OracleServiceError):
    """Rate limit exceeded."""

    def __init__(
        self,
        service_name: str,
        limit: int,
        period_seconds: int,
        retry_after_seconds: Optional[int] = None,
    ):
        self.service_name = service_name
        self.limit = limit
        self.period_seconds = period_seconds
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            message=f"Rate limit exceeded for {service_name}: {limit} requests per {period_seconds}s",
            error_code="RATE_LIMIT_EXCEEDED",
            details={
                "service": service_name,
                "limit": limit,
                "period_seconds": period_seconds,
                "retry_after_seconds": retry_after_seconds,
            },
        )


class UserRateLimitError(RateLimitError):
    """Per-user rate limit exceeded."""

    def __init__(self, user_id: str, limit: int, period_seconds: int):
        self.user_id = user_id
        super().__init__(
            service_name=f"user:{user_id}",
            limit=limit,
            period_seconds=period_seconds,
        )
        self.error_code = "USER_RATE_LIMIT_EXCEEDED"


# ===========================================
# Circuit Breaker Exceptions
# ===========================================


class CircuitBreakerOpenError(OracleServiceError):
    """Circuit breaker is open - service unavailable."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        super().__init__(
            message=f"Circuit breaker open for {service_name}. Service temporarily unavailable.",
            error_code="CIRCUIT_BREAKER_OPEN",
            details={"service": service_name},
        )


# ===========================================
# External API Exceptions
# ===========================================


class ExternalAPIError(OracleServiceError):
    """Error from external API call."""

    def __init__(
        self,
        service_name: str,
        status_code: Optional[int] = None,
        message: Optional[str] = None,
    ):
        self.service_name = service_name
        self.status_code = status_code
        super().__init__(
            message=message or f"External API error from {service_name}",
            error_code="EXTERNAL_API_ERROR",
            details={
                "service": service_name,
                "status_code": status_code,
            },
        )


class TavilyAPIError(ExternalAPIError):
    """Error from Tavily API."""

    def __init__(self, status_code: Optional[int] = None, message: Optional[str] = None):
        super().__init__(
            service_name="tavily",
            status_code=status_code,
            message=message or "Tavily API error",
        )
        self.error_code = "TAVILY_API_ERROR"


class GitHubAPIError(ExternalAPIError):
    """Error from GitHub API."""

    def __init__(self, status_code: Optional[int] = None, message: Optional[str] = None):
        super().__init__(
            service_name="github",
            status_code=status_code,
            message=message or "GitHub API error",
        )
        self.error_code = "GITHUB_API_ERROR"


class AnthropicAPIError(ExternalAPIError):
    """Error from Anthropic API."""

    def __init__(self, status_code: Optional[int] = None, message: Optional[str] = None):
        super().__init__(
            service_name="anthropic",
            status_code=status_code,
            message=message or "Anthropic API error",
        )
        self.error_code = "ANTHROPIC_API_ERROR"


# ===========================================
# Validation Exceptions
# ===========================================


class ValidationError(OracleServiceError):
    """Input validation error."""

    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details={"field": field} if field else {},
        )


class InputTooLongError(ValidationError):
    """Input exceeds maximum length."""

    def __init__(self, field: str, max_length: int, actual_length: int):
        super().__init__(
            message=f"Field '{field}' exceeds maximum length of {max_length} (got {actual_length})",
            field=field,
        )
        self.error_code = "INPUT_TOO_LONG"
        self.details = {
            "field": field,
            "max_length": max_length,
            "actual_length": actual_length,
        }


# ===========================================
# Analytics Exceptions
# ===========================================


class AnalyticsError(OracleServiceError):
    """Base exception for analytics-related errors."""

    def __init__(self, message: str, event_id: Optional[str] = None, **kwargs):
        self.event_id = event_id
        super().__init__(message, error_code="ANALYTICS_ERROR", **kwargs)


class AnalyticsNotFoundError(AnalyticsError):
    """Analytics data not found for event."""

    def __init__(self, event_id: str):
        super().__init__(
            message=f"Analytics data not found for event {event_id}",
            event_id=event_id,
            details={"event_id": event_id},
        )
        self.error_code = "ANALYTICS_NOT_FOUND"
