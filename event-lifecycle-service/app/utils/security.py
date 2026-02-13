# app/utils/security.py
"""
Security utilities for privacy, GDPR compliance, and input validation.

This module provides security-focused validation functions to prevent:
- Open redirect attacks
- XSS via malicious URLs
- DoS via oversized inputs
- Injection attacks
"""

import re
import hashlib
from typing import Optional, List, Tuple
from urllib.parse import urlparse
from app.core.config import settings


# =============================================================================
# INPUT VALIDATION CONSTANTS
# =============================================================================

# Allowed URL schemes for media/image URLs
ALLOWED_MEDIA_SCHEMES = {"https", "http"}

# Allowed URL schemes for click/redirect URLs (HTTPS only for security)
ALLOWED_REDIRECT_SCHEMES = {"https"}

# Blocked domains for redirect URLs (URL shorteners, suspicious domains)
BLOCKED_REDIRECT_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "adf.ly", "j.mp", "tr.im",
}

# Maximum lengths for various fields
MAX_LENGTHS = {
    "name": 255,
    "title": 255,
    "description": 5000,
    "url": 2048,
    "context": 500,
    "currency": 3,
    "aspect_ratio": 10,
}

# Maximum array sizes
MAX_ARRAY_SIZES = {
    "placements": 20,
    "target_sessions": 100,
    "target_ticket_tiers": 50,
    "impressions": 100,
}

# Valid enum values
VALID_CONTENT_TYPES = {"BANNER", "VIDEO", "SPONSORED_SESSION", "INTERSTITIAL"}
VALID_OFFER_TYPES = {"TICKET_UPGRADE", "MERCHANDISE", "EXCLUSIVE_CONTENT", "SERVICE"}
VALID_PLACEMENTS = {"CHECKOUT", "POST_PURCHASE", "IN_EVENT", "EMAIL", "EVENT_HERO", "SESSION_BREAK", "SIDEBAR"}
VALID_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CNY", "INR", "BRL", "MXN", "KRW", "SGD", "HKD", "CHF", "SEK", "NOK", "DKK", "NZD"}

# Numeric limits
MAX_PRICE = 1000000.00  # $1M max
MAX_QUANTITY = 100
MAX_WEIGHT = 1000
MAX_FREQUENCY_CAP = 100
MAX_DISPLAY_DURATION = 300  # 5 minutes max
MAX_QUERY_LIMIT = 100


# =============================================================================
# URL VALIDATION
# =============================================================================

def validate_url(
    url: str,
    field_name: str = "url",
    allow_http: bool = True,
    allow_redirects: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Validate a URL for security.

    Args:
        url: The URL to validate
        field_name: Name of the field for error messages
        allow_http: Whether to allow HTTP (not just HTTPS)
        allow_redirects: Whether this URL will be used for redirects (stricter checks)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return True, None  # Empty URL is valid (optional field)

    # Check length
    if len(url) > MAX_LENGTHS["url"]:
        return False, f"{field_name} exceeds maximum length of {MAX_LENGTHS['url']} characters"

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception:
        return False, f"Invalid {field_name} format"

    # Check for dangerous schemes first
    scheme_lower = parsed.scheme.lower()
    if scheme_lower in ("javascript", "data", "vbscript", "file"):
        return False, f"{field_name} contains dangerous scheme"

    # Check scheme
    if allow_redirects:
        allowed_schemes = ALLOWED_REDIRECT_SCHEMES
    else:
        allowed_schemes = ALLOWED_MEDIA_SCHEMES if allow_http else ALLOWED_REDIRECT_SCHEMES

    if scheme_lower not in allowed_schemes:
        if allow_redirects or not allow_http:
            return False, f"{field_name} must use HTTPS"
        return False, f"{field_name} must use HTTP or HTTPS"

    # Check hostname exists
    if not parsed.netloc:
        return False, f"{field_name} must have a valid hostname"

    # For redirect URLs, apply stricter checks
    if allow_redirects:
        hostname = parsed.netloc.lower().split(':')[0]  # Remove port if present
        # Block URL shorteners
        for blocked in BLOCKED_REDIRECT_DOMAINS:
            if hostname == blocked or hostname.endswith(f".{blocked}"):
                return False, f"{field_name} uses a blocked domain (URL shorteners not allowed)"

    return True, None


# =============================================================================
# STRING VALIDATION
# =============================================================================

def validate_string_length(
    value: Optional[str],
    field_name: str,
    max_length: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate string length.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if value is None:
        return True, None

    max_len = max_length or MAX_LENGTHS.get(field_name, 1000)

    if len(value) > max_len:
        return False, f"{field_name} exceeds maximum length of {max_len} characters"

    return True, None


# =============================================================================
# ARRAY VALIDATION
# =============================================================================

def validate_array_size(
    arr: Optional[List],
    field_name: str,
    max_size: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate array size to prevent DoS.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if arr is None:
        return True, None

    max_len = max_size or MAX_ARRAY_SIZES.get(field_name, 50)

    if len(arr) > max_len:
        return False, f"{field_name} exceeds maximum size of {max_len} items"

    return True, None


# =============================================================================
# ENUM VALIDATION
# =============================================================================

def validate_enum(
    value: Optional[str],
    field_name: str,
    valid_values: set
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a value is in an allowed enum set.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if value is None:
        return True, None

    if value.upper() not in valid_values:
        valid_list = ", ".join(sorted(valid_values))
        return False, f"Invalid {field_name}. Must be one of: {valid_list}"

    return True, None


# =============================================================================
# NUMERIC VALIDATION
# =============================================================================

def validate_positive_number(
    value: Optional[float],
    field_name: str,
    max_value: Optional[float] = None,
    allow_zero: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a number is positive and within limits.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if value is None:
        return True, None

    min_val = 0 if allow_zero else 0.01
    if value < min_val:
        return False, f"{field_name} must be {'non-negative' if allow_zero else 'positive'}"

    if max_value is not None and value > max_value:
        return False, f"{field_name} exceeds maximum value of {max_value}"

    return True, None


def validate_quantity(quantity: int) -> Tuple[bool, Optional[str]]:
    """
    Validate purchase quantity.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if quantity is None:
        return False, "Quantity is required"

    if quantity < 1:
        return False, "Quantity must be at least 1"

    if quantity > MAX_QUANTITY:
        return False, f"Quantity cannot exceed {MAX_QUANTITY}"

    return True, None


def validate_limit(limit: Optional[int], default: int = 10) -> int:
    """
    Validate and sanitize a query limit parameter.

    Returns:
        A safe limit value
    """
    if limit is None:
        return default

    if limit < 1:
        return default

    if limit > MAX_QUERY_LIMIT:
        return MAX_QUERY_LIMIT

    return limit


# =============================================================================
# ERROR HANDLING
# =============================================================================

def sanitize_error_message(error: Exception) -> str:
    """
    Sanitize an error message to prevent information leakage.

    Returns:
        A safe error message string
    """
    # Map of known safe error patterns
    safe_patterns = {
        "stripe": "Payment processing error. Please try again.",
        "connection": "Service temporarily unavailable. Please try again.",
        "timeout": "Request timed out. Please try again.",
        "not found": "Resource not found.",
        "invalid": "Invalid request.",
        "card": "Card error. Please check your payment details.",
        "expired": "Resource has expired.",
        "inventory": "Insufficient inventory available.",
    }

    error_lower = str(error).lower()

    for pattern, safe_msg in safe_patterns.items():
        if pattern in error_lower:
            return safe_msg

    # Default generic message
    return "An error occurred. Please try again later."


# =============================================================================
# INPUT VALIDATION HELPERS
# =============================================================================

def validate_ad_input(ad_input) -> List[str]:
    """
    Validate all fields of an ad input.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Validate URLs
    valid, err = validate_url(ad_input.media_url, "media_url", allow_http=True)
    if not valid:
        errors.append(err)

    valid, err = validate_url(ad_input.click_url, "click_url", allow_http=False, allow_redirects=True)
    if not valid:
        errors.append(err)

    # Validate strings
    valid, err = validate_string_length(ad_input.name, "name")
    if not valid:
        errors.append(err)

    # Validate enums
    valid, err = validate_enum(ad_input.content_type, "content_type", VALID_CONTENT_TYPES)
    if not valid:
        errors.append(err)

    # Validate arrays
    if hasattr(ad_input, 'placements') and ad_input.placements:
        valid, err = validate_array_size(ad_input.placements, "placements")
        if not valid:
            errors.append(err)
        else:
            # Validate each placement
            for p in ad_input.placements:
                valid, err = validate_enum(p, "placement", VALID_PLACEMENTS)
                if not valid:
                    errors.append(err)
                    break

    if hasattr(ad_input, 'target_sessions') and ad_input.target_sessions:
        valid, err = validate_array_size(ad_input.target_sessions, "target_sessions")
        if not valid:
            errors.append(err)

    # Validate numbers
    if hasattr(ad_input, 'weight') and ad_input.weight is not None:
        valid, err = validate_positive_number(ad_input.weight, "weight", MAX_WEIGHT)
        if not valid:
            errors.append(err)

    if hasattr(ad_input, 'frequency_cap') and ad_input.frequency_cap is not None:
        valid, err = validate_positive_number(ad_input.frequency_cap, "frequency_cap", MAX_FREQUENCY_CAP)
        if not valid:
            errors.append(err)

    if hasattr(ad_input, 'display_duration_seconds') and ad_input.display_duration_seconds is not None:
        valid, err = validate_positive_number(
            ad_input.display_duration_seconds, "display_duration_seconds", MAX_DISPLAY_DURATION
        )
        if not valid:
            errors.append(err)

    # Validate aspect_ratio format (must be "W:H" where W and H are positive integers)
    if hasattr(ad_input, 'aspect_ratio') and ad_input.aspect_ratio is not None:
        import re
        if not re.match(r'^\d{1,4}:\d{1,4}$', ad_input.aspect_ratio):
            errors.append("aspect_ratio must be in 'W:H' format (e.g. '16:9')")
        else:
            w, h = ad_input.aspect_ratio.split(':')
            if int(w) == 0 or int(h) == 0:
                errors.append("aspect_ratio width and height must be greater than 0")

    return errors


def validate_offer_input(offer_input) -> List[str]:
    """
    Validate all fields of an offer input.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Validate URLs
    if hasattr(offer_input, 'image_url') and offer_input.image_url:
        valid, err = validate_url(offer_input.image_url, "image_url", allow_http=True)
        if not valid:
            errors.append(err)

    # Validate strings
    if hasattr(offer_input, 'title') and offer_input.title:
        valid, err = validate_string_length(offer_input.title, "title")
        if not valid:
            errors.append(err)

    if hasattr(offer_input, 'description') and offer_input.description:
        valid, err = validate_string_length(offer_input.description, "description")
        if not valid:
            errors.append(err)

    # Validate enums
    if hasattr(offer_input, 'offer_type') and offer_input.offer_type:
        valid, err = validate_enum(offer_input.offer_type, "offer_type", VALID_OFFER_TYPES)
        if not valid:
            errors.append(err)

    if hasattr(offer_input, 'placement') and offer_input.placement:
        valid, err = validate_enum(offer_input.placement, "placement", VALID_PLACEMENTS)
        if not valid:
            errors.append(err)

    if hasattr(offer_input, 'currency') and offer_input.currency:
        valid, err = validate_enum(offer_input.currency.upper(), "currency", VALID_CURRENCIES)
        if not valid:
            errors.append(err)

    # Validate arrays
    if hasattr(offer_input, 'target_sessions') and offer_input.target_sessions:
        valid, err = validate_array_size(offer_input.target_sessions, "target_sessions")
        if not valid:
            errors.append(err)

    if hasattr(offer_input, 'target_ticket_tiers') and offer_input.target_ticket_tiers:
        valid, err = validate_array_size(offer_input.target_ticket_tiers, "target_ticket_tiers")
        if not valid:
            errors.append(err)

    # Validate numbers
    if hasattr(offer_input, 'price') and offer_input.price is not None:
        valid, err = validate_positive_number(offer_input.price, "price", MAX_PRICE)
        if not valid:
            errors.append(err)

    if hasattr(offer_input, 'original_price') and offer_input.original_price is not None:
        valid, err = validate_positive_number(offer_input.original_price, "original_price", MAX_PRICE)
        if not valid:
            errors.append(err)

    if hasattr(offer_input, 'inventory_total') and offer_input.inventory_total is not None:
        valid, err = validate_positive_number(offer_input.inventory_total, "inventory_total", 1000000, allow_zero=False)
        if not valid:
            errors.append(err)

    # M-CQ3: Cross-field validation (original_price must be >= price)
    if (hasattr(offer_input, 'original_price') and offer_input.original_price is not None
            and hasattr(offer_input, 'price') and offer_input.price is not None):
        if offer_input.original_price < offer_input.price:
            errors.append("Original price must be >= price")

    return errors


# =============================================================================
# GDPR/PRIVACY FUNCTIONS (existing)
# =============================================================================


def anonymize_ip(ip_address: Optional[str]) -> Optional[str]:
    """
    Anonymize IP address for GDPR compliance.

    Uses SHA-256 hashing with a secret salt to create a consistent but
    non-reversible anonymized identifier.

    Args:
        ip_address: The IP address to anonymize (IPv4 or IPv6)

    Returns:
        A 16-character hexadecimal hash, or None if input is None

    Example:
        >>> anonymize_ip("192.168.1.1")
        'a3f5e8c2d1b4f6e9'

    Note:
        - Same IP always produces same hash (for analytics)
        - Cannot be reversed to original IP
        - Change IP_HASH_SALT in production for security
    """
    if not ip_address:
        return None

    # Combine salt with IP address
    salted_input = f"{settings.IP_HASH_SALT}{ip_address}"

    # Create SHA-256 hash
    hash_object = hashlib.sha256(salted_input.encode('utf-8'))
    hash_hex = hash_object.hexdigest()

    # Return first 16 characters (sufficient entropy)
    return hash_hex[:16]


def anonymize_user_agent(user_agent: Optional[str]) -> Optional[str]:
    """
    Optionally anonymize or truncate user agent string.

    For now, we keep the full user agent for analytics, but this function
    can be enhanced to remove potentially identifying information.

    Args:
        user_agent: The user agent string

    Returns:
        The user agent (currently unchanged)

    Future enhancement:
        - Remove version numbers that are too specific
        - Generalize browser/OS versions
    """
    # For now, return as-is
    # Future: implement user agent anonymization if needed
    return user_agent
