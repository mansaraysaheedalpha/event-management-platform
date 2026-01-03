# app/utils/security.py
"""
Security utilities for privacy and GDPR compliance.
"""

import hashlib
from typing import Optional
from app.core.config import settings


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
