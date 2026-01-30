"""
API Middleware for Conference Contrarian.

Provides:
- Request ID tracking and logging
- Structured error handling
- Response standardization
- Request timing
- Rate limiting for API endpoints
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Rate limiting imports
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Context variable for request ID
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

logger = logging.getLogger(__name__)


def get_current_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return request_id_var.get()


# =============================================================================
# Custom Exceptions
# =============================================================================

class ApiException(Exception):
    """Base exception for API errors."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[dict] = None
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class ValidationException(ApiException):
    """400 Bad Request - Invalid input."""

    def __init__(self, message: str = "Invalid request", details: Optional[dict] = None):
        super().__init__(400, "VALIDATION_ERROR", message, details)


class NotFoundException(ApiException):
    """404 Not Found."""

    def __init__(self, resource: str = "Resource", identifier: Optional[str] = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} '{identifier}' not found"
        super().__init__(404, "NOT_FOUND", message, {"resource": resource})


class ExternalApiException(ApiException):
    """502 Bad Gateway - External API failure."""

    def __init__(self, service: str, message: Optional[str] = None):
        error_message = message or f"External service '{service}' is unavailable"
        super().__init__(502, "EXTERNAL_API_ERROR", error_message, {"service": service})


class RateLimitException(ApiException):
    """429 Too Many Requests."""

    def __init__(self, retry_after: Optional[int] = None):
        super().__init__(
            429,
            "RATE_LIMIT_EXCEEDED",
            "Too many requests. Please try again later.",
            {"retry_after": retry_after}
        )


# =============================================================================
# Response Helpers
# =============================================================================

def error_response(
    code: str,
    message: str,
    details: Optional[dict] = None,
    request_id: Optional[str] = None
) -> dict:
    """Create a standardized error response."""
    response = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        response["error"]["details"] = details
    if request_id:
        response["request_id"] = request_id
    return response


def success_response(
    data: Any = None,
    message: Optional[str] = None,
    meta: Optional[dict] = None
) -> dict:
    """Create a standardized success response."""
    response: dict = {"success": True}
    if data is not None:
        response["data"] = data
    if message:
        response["message"] = message
    if meta:
        response["meta"] = meta
    return response


def paginated_response(
    items: list,
    page: int,
    page_size: int,
    total: int
) -> dict:
    """Create a standardized paginated response."""
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return success_response(
        data=items,
        meta={
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    )


# =============================================================================
# Logging Middleware
# =============================================================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for structured request logging.

    Features:
    - Unique request ID per request (UUID4)
    - Request/response timing
    - Structured JSON logging
    - Request ID in response headers
    """

    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]

        # Store in context and request state
        token = request_id_var.set(request_id)
        request.state.request_id = request_id

        # Log request
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "event": "request",
            "method": request.method,
            "path": request.url.path,
        }
        logger.info(json.dumps(log_entry))

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Log response
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "event": "response",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            }
            logger.info(json.dumps(log_entry))

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "event": "error",
                "method": request.method,
                "path": request.url.path,
                "error_type": type(exc).__name__,
                "duration_ms": duration_ms,
            }
            logger.error(json.dumps(log_entry))
            raise

        finally:
            request_id_var.reset(token)


# =============================================================================
# Exception Handlers (register in main.py)
# =============================================================================

async def api_exception_handler(request: Request, exc: ApiException) -> JSONResponse:
    """Handle custom API exceptions."""
    request_id = getattr(request.state, 'request_id', None) or get_current_request_id()

    logger.warning(f"[{request_id}] API Error [{exc.code}]: {exc.message}")

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            exc.code,
            exc.message,
            exc.details,
            request_id
        ),
        headers={"X-Request-ID": request_id} if request_id else {}
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle Pydantic validation errors."""
    from fastapi.exceptions import RequestValidationError

    request_id = getattr(request.state, 'request_id', None) or get_current_request_id()

    if isinstance(exc, RequestValidationError):
        errors = exc.errors()
        details = {
            "validation_errors": [
                {
                    "field": ".".join(str(loc) for loc in err.get("loc", [])),
                    "message": err.get("msg", "Validation error"),
                    "type": err.get("type", "unknown")
                }
                for err in errors
            ]
        }
        return JSONResponse(
            status_code=400,
            content=error_response(
                "VALIDATION_ERROR",
                "Request validation failed",
                details,
                request_id
            ),
            headers={"X-Request-ID": request_id} if request_id else {}
        )
    raise exc


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with generic error response."""
    request_id = getattr(request.state, 'request_id', None) or get_current_request_id()

    logger.exception(f"[{request_id}] Unhandled exception: {type(exc).__name__}: {exc}")

    return JSONResponse(
        status_code=500,
        content=error_response(
            "INTERNAL_ERROR",
            "An unexpected error occurred",
            None,
            request_id
        ),
        headers={"X-Request-ID": request_id} if request_id else {}
    )


# =============================================================================
# Rate Limiting Configuration
# =============================================================================

def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.

    Handles common proxy headers (X-Forwarded-For, X-Real-IP) for deployments
    behind load balancers (Railway, Vercel, etc.).
    """
    # Check X-Forwarded-For header (common with proxies/load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
        # The first IP is the original client
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header (nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct connection IP
    if request.client:
        return request.client.host

    return "unknown"


# Create the limiter instance with IP-based key function
limiter = Limiter(key_func=get_client_ip)

# Rate limit constants
RATE_LIMIT_AI_ENDPOINTS = "10/minute"     # AI analysis endpoints (rate limited to prevent abuse)
RATE_LIMIT_STANDARD_ENDPOINTS = "30/minute"  # Standard API endpoints


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Handle rate limit exceeded errors with proper HTTP 429 response.

    Returns a JSON response with:
    - 429 status code
    - Retry-After header indicating when the client can retry
    - Structured error response with details
    """
    request_id = getattr(request.state, 'request_id', None) or get_current_request_id()

    # Extract retry-after from the exception detail if available
    # slowapi format: "Rate limit exceeded: X per Y"
    retry_after = 60  # Default to 60 seconds

    # Log the rate limit event
    logger.warning(
        f"[{request_id}] Rate limit exceeded for IP: {get_client_ip(request)} "
        f"on path: {request.url.path}"
    )

    return JSONResponse(
        status_code=429,
        content=error_response(
            code="RATE_LIMIT_EXCEEDED",
            message="Too many requests. Please slow down and try again later.",
            details={
                "retry_after_seconds": retry_after,
                "limit": str(exc.detail) if hasattr(exc, 'detail') else "Rate limit exceeded"
            },
            request_id=request_id
        ),
        headers={
            "X-Request-ID": request_id or "",
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(exc.detail) if hasattr(exc, 'detail') else "unknown"
        }
    )
