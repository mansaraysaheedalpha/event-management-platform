"""
Comprehensive Error Handler Middleware

Provides centralized error handling for the agent service with:
- Structured error responses
- Error logging with context
- Error categorization
- Retry logic for transient failures
"""

import logging
import traceback
from typing import Callable, Optional
from datetime import datetime
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
import httpx

logger = logging.getLogger(__name__)


class ErrorCategory:
    """Error categories for structured error handling"""
    VALIDATION = "validation_error"
    DATABASE = "database_error"
    EXTERNAL_SERVICE = "external_service_error"
    RATE_LIMIT = "rate_limit_error"
    AUTHENTICATION = "authentication_error"
    NOT_FOUND = "not_found_error"
    INTERNAL = "internal_error"
    TIMEOUT = "timeout_error"


class AppError(Exception):
    """Base application error with structured information"""

    def __init__(
        self,
        message: str,
        category: str = ErrorCategory.INTERNAL,
        status_code: int = 500,
        details: Optional[dict] = None,
        retry_after: Optional[int] = None
    ):
        self.message = message
        self.category = category
        self.status_code = status_code
        self.details = details or {}
        self.retry_after = retry_after
        super().__init__(self.message)


class DatabaseError(AppError):
    """Database-related errors"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.DATABASE,
            status_code=503,
            details=details,
            retry_after=30
        )


class ExternalServiceError(AppError):
    """External service errors (LLM API, etc.)"""
    def __init__(self, message: str, service: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.EXTERNAL_SERVICE,
            status_code=502,
            details={"service": service, **(details or {})},
            retry_after=10
        )


class RateLimitError(AppError):
    """Rate limit exceeded errors"""
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(
            message=message,
            category=ErrorCategory.RATE_LIMIT,
            status_code=429,
            retry_after=retry_after
        )


class ValidationError(AppError):
    """Validation errors"""
    def __init__(self, message: str, field: Optional[str] = None):
        details = {"field": field} if field else {}
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            status_code=400,
            details=details
        )


async def error_handler_middleware(request: Request, call_next: Callable) -> Response:
    """
    Global error handling middleware.

    Catches all unhandled exceptions and returns structured error responses.
    """
    try:
        response = await call_next(request)
        return response

    except AppError as e:
        # Application errors - already structured
        return handle_app_error(e, request)

    except RequestValidationError as e:
        # FastAPI validation errors
        return handle_validation_error(e, request)

    except SQLAlchemyError as e:
        # Database errors
        return handle_database_error(e, request)

    except (RedisError, RedisConnectionError) as e:
        # Redis errors
        return handle_redis_error(e, request)

    except httpx.TimeoutException as e:
        # HTTP timeout errors
        return handle_timeout_error(e, request)

    except httpx.HTTPStatusError as e:
        # HTTP errors from external services
        return handle_http_error(e, request)

    except Exception as e:
        # Catch-all for unexpected errors
        return handle_unexpected_error(e, request)


def handle_app_error(error: AppError, request: Request) -> JSONResponse:
    """Handle structured application errors"""

    logger.error(
        f"Application error: {error.category}",
        extra={
            "category": error.category,
            "message": error.message,
            "status_code": error.status_code,
            "path": request.url.path,
            "method": request.method,
            "details": error.details
        }
    )

    response_data = {
        "error": {
            "category": error.category,
            "message": error.message,
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path,
            **error.details
        }
    }

    headers = {}
    if error.retry_after:
        headers["Retry-After"] = str(error.retry_after)

    return JSONResponse(
        status_code=error.status_code,
        content=response_data,
        headers=headers
    )


def handle_validation_error(error: RequestValidationError, request: Request) -> JSONResponse:
    """Handle FastAPI validation errors"""

    errors = []
    for err in error.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in err["loc"]),
            "message": err["msg"],
            "type": err["type"]
        })

    logger.warning(
        f"Validation error on {request.url.path}",
        extra={"errors": errors, "method": request.method}
    )

    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "category": ErrorCategory.VALIDATION,
                "message": "Request validation failed",
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path,
                "validation_errors": errors
            }
        }
    )


def handle_database_error(error: SQLAlchemyError, request: Request) -> JSONResponse:
    """Handle database errors"""

    # Determine error type
    is_connection_error = isinstance(error, OperationalError)
    is_integrity_error = isinstance(error, IntegrityError)

    if is_connection_error:
        message = "Database connection failed. Please try again."
        retry_after = 30
    elif is_integrity_error:
        message = "Database constraint violation. Check your input data."
        retry_after = None
    else:
        message = "Database operation failed. Please try again."
        retry_after = 10

    logger.error(
        f"Database error: {type(error).__name__}",
        extra={
            "error": str(error),
            "path": request.url.path,
            "method": request.method,
            "is_connection_error": is_connection_error,
            "is_integrity_error": is_integrity_error
        },
        exc_info=True
    )

    headers = {}
    if retry_after:
        headers["Retry-After"] = str(retry_after)

    return JSONResponse(
        status_code=503 if is_connection_error else 500,
        content={
            "error": {
                "category": ErrorCategory.DATABASE,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path,
                "type": type(error).__name__
            }
        },
        headers=headers
    )


def handle_redis_error(error: Exception, request: Request) -> JSONResponse:
    """Handle Redis connection errors"""

    logger.error(
        f"Redis error: {type(error).__name__}",
        extra={
            "error": str(error),
            "path": request.url.path,
            "method": request.method
        },
        exc_info=True
    )

    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "category": ErrorCategory.EXTERNAL_SERVICE,
                "message": "Cache service temporarily unavailable. Please try again.",
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path,
                "service": "redis"
            }
        },
        headers={"Retry-After": "30"}
    )


def handle_timeout_error(error: httpx.TimeoutException, request: Request) -> JSONResponse:
    """Handle HTTP timeout errors"""

    logger.error(
        f"Timeout error on {request.url.path}",
        extra={
            "error": str(error),
            "method": request.method
        }
    )

    return JSONResponse(
        status_code=504,
        content={
            "error": {
                "category": ErrorCategory.TIMEOUT,
                "message": "Request timed out. Please try again.",
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path
            }
        },
        headers={"Retry-After": "10"}
    )


def handle_http_error(error: httpx.HTTPStatusError, request: Request) -> JSONResponse:
    """Handle HTTP errors from external services"""

    logger.error(
        f"External service error: {error.response.status_code}",
        extra={
            "url": str(error.request.url),
            "status_code": error.response.status_code,
            "path": request.url.path,
            "method": request.method
        }
    )

    return JSONResponse(
        status_code=502,
        content={
            "error": {
                "category": ErrorCategory.EXTERNAL_SERVICE,
                "message": "External service error. Please try again.",
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path,
                "upstream_status": error.response.status_code
            }
        },
        headers={"Retry-After": "10"}
    )


def handle_unexpected_error(error: Exception, request: Request) -> JSONResponse:
    """Handle unexpected errors"""

    # Get traceback for logging
    tb = traceback.format_exc()

    logger.critical(
        f"Unexpected error: {type(error).__name__}",
        extra={
            "error": str(error),
            "traceback": tb,
            "path": request.url.path,
            "method": request.method
        },
        exc_info=True
    )

    # Don't expose internal details in production
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "category": ErrorCategory.INTERNAL,
                "message": "An unexpected error occurred. Our team has been notified.",
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path,
                "error_id": datetime.utcnow().strftime("%Y%m%d%H%M%S")  # For support tracking
            }
        }
    )


# Exception handlers for FastAPI
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """FastAPI exception handler for AppError"""
    return handle_app_error(exc, request)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI exception handler for validation errors"""
    return handle_validation_error(exc, request)
