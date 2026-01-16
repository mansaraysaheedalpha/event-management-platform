# app/core/limiter.py
"""
Rate limiter configuration module.
Separated to avoid circular imports.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiter configuration - uses IP address as key
limiter = Limiter(key_func=get_remote_address)
