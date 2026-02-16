"""
JWT-based QR code signing for offline-verifiable tickets.

QR format versions:
  v1 (legacy): pipe-delimited "{id}|{code}|{event_id}|{sha256_hash[:8]}"
  v2 (HS256):  JWT signed with shared HMAC secret (server-side verify only)
  v3 (RS256):  JWT signed with per-event RSA private key (offline-verifiable
               with public key — safe to distribute to scanner apps)

v3 enables offline check-in: scanner apps fetch the event's public key once,
then verify QR codes locally without network. Critical for African venues
where MTN/Airtel networks drop under crowd load.

Key persistence:
  RSA keypairs are persisted in Redis so they survive server restarts.
  An in-memory dict acts as an L1 cache to avoid Redis round-trips on
  every QR code generation. Keys are stored at:
    qr_keys:{event_id}:private
    qr_keys:{event_id}:public
"""

import jwt
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Tuple
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

# HS256 legacy secret (kept for backward compat with existing v2 QR codes)
QR_SIGNING_SECRET = os.environ.get(
    "QR_SIGNING_SECRET",
    "CHANGE-ME-IN-PRODUCTION-use-a-64-char-random-string",
)

# L1 in-memory cache: event_id -> (private_pem, public_pem)
_event_keys: Dict[str, Tuple[str, str]] = {}

_REDIS_KEY_PREFIX = "qr_keys"


def _get_redis():
    """Get a Redis client, returning None if unavailable."""
    try:
        from app.db.redis import redis_client
        redis_client.ping()
        return redis_client
    except Exception:
        return None


def _generate_rsa_keypair() -> Tuple[str, str]:
    """Generate a 2048-bit RSA key pair and return PEM-encoded strings."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


def ensure_event_keypair(event_id: str) -> Tuple[str, str]:
    """Get or create an RSA key pair for an event.

    Lookup order:
      1. In-memory cache (fast, per-process)
      2. Redis (shared across workers, survives restarts)
      3. Generate new keypair → store in Redis + memory

    Returns:
        Tuple of (private_key_pem, public_key_pem).
    """
    # L1: in-memory cache
    if event_id in _event_keys:
        return _event_keys[event_id]

    # L2: Redis
    r = _get_redis()
    if r:
        try:
            priv = r.get(f"{_REDIS_KEY_PREFIX}:{event_id}:private")
            pub = r.get(f"{_REDIS_KEY_PREFIX}:{event_id}:public")
            if priv and pub:
                _event_keys[event_id] = (priv, pub)
                logger.debug(f"Loaded RSA keypair from Redis for event {event_id}")
                return _event_keys[event_id]
        except Exception as e:
            logger.warning(f"Redis read failed for event {event_id} keypair: {e}")

    # Generate new keypair
    logger.info(f"Generating RSA keypair for event {event_id}")
    private_pem, public_pem = _generate_rsa_keypair()

    # Persist to Redis (no expiry — keys are needed for the lifetime of QR codes)
    if r:
        try:
            r.set(f"{_REDIS_KEY_PREFIX}:{event_id}:private", private_pem)
            r.set(f"{_REDIS_KEY_PREFIX}:{event_id}:public", public_pem)
            logger.info(f"Persisted RSA keypair to Redis for event {event_id}")
        except Exception as e:
            logger.error(f"Failed to persist keypair to Redis for event {event_id}: {e}")

    _event_keys[event_id] = (private_pem, public_pem)
    return _event_keys[event_id]


def get_public_key_for_event(event_id: str) -> str:
    """Get the RS256 public key PEM for an event.

    Safe to distribute to scanner apps — public keys cannot forge signatures.
    """
    _, public_pem = ensure_event_keypair(event_id)
    return public_pem


def sign_ticket_qr(
    ticket_id: str,
    ticket_code: str,
    event_id: str,
    user_id: Optional[str],
    attendee_name: str,
    event_end_date: Optional[datetime] = None,
) -> str:
    """Generate an RS256-signed JWT for embedding in a QR code.

    Claims:
    - tid: ticket ID (primary key)
    - tcode: human-readable ticket code (TKT-XXXXXX-XX)
    - eid: event ID the ticket belongs to
    - sub: user ID of ticket owner (nullable for guest tickets)
    - name: attendee name for display on scanner UI
    - iat: issued-at timestamp
    - exp: expiration (24h after event end, or 30 days if no end date)
    - v: QR format version (3 = RS256)

    Returns:
        Compact JWT string suitable for QR code encoding.
    """
    now = datetime.now(timezone.utc)

    if event_end_date:
        exp = event_end_date + timedelta(hours=24)
    else:
        exp = now + timedelta(days=30)

    payload = {
        "tid": ticket_id,
        "tcode": ticket_code,
        "eid": event_id,
        "sub": user_id,
        "name": attendee_name,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "v": 3,
    }

    private_pem, _ = ensure_event_keypair(event_id)
    return jwt.encode(payload, private_pem, algorithm="RS256")


def sign_live_qr(
    ticket_code: str,
    event_id: str,
    user_id: Optional[str],
    attendee_name: str,
    ttl_seconds: int = 300,
) -> str:
    """Generate a short-lived RS256 JWT for live QR display.

    Same claims as sign_ticket_qr but with a tight expiration (default 5 min).
    The "live" claim distinguishes this from static QR codes. Screenshots
    of a live QR expire quickly, preventing replay attacks.

    Args:
        ticket_code: Human-readable ticket code.
        event_id: Event the ticket belongs to.
        user_id: Ticket owner's user ID.
        attendee_name: For display on scanner UI.
        ttl_seconds: Seconds until the JWT expires (default 300 = 5 min).

    Returns:
        Compact JWT string.
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=ttl_seconds)

    payload = {
        "tcode": ticket_code,
        "eid": event_id,
        "sub": user_id,
        "name": attendee_name,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "v": 3,
        "live": True,
    }

    private_pem, _ = ensure_event_keypair(event_id)
    return jwt.encode(payload, private_pem, algorithm="RS256")


def verify_ticket_qr(token: str, public_key_pem: Optional[str] = None) -> Optional[dict]:
    """Verify a signed QR token and return decoded claims.

    Supports both RS256 (v3, offline-capable) and HS256 (v2, legacy).
    When public_key_pem is provided, uses RS256 verification first.
    Falls back to HS256 for backward compatibility with existing QR codes.

    Args:
        token: The JWT string from the QR code.
        public_key_pem: Optional RS256 public key. If provided, try RS256 first.

    Returns:
        Decoded JWT payload dict if valid, or None if invalid/expired.
    """
    # Try RS256 first (v3 tokens)
    if public_key_pem:
        try:
            return jwt.decode(token, public_key_pem, algorithms=["RS256"])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            pass

    # Try RS256 with cached event key by peeking at the unverified payload
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        event_id = unverified.get("eid")
        if event_id:
            # Check L1 (memory) then L2 (Redis) for the public key
            pub_pem = None
            if event_id in _event_keys:
                _, pub_pem = _event_keys[event_id]
            else:
                r = _get_redis()
                if r:
                    try:
                        pub_pem = r.get(f"{_REDIS_KEY_PREFIX}:{event_id}:public")
                    except Exception:
                        pass
            if pub_pem:
                try:
                    return jwt.decode(token, pub_pem, algorithms=["RS256"])
                except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                    pass
    except Exception:
        pass

    # Fall back to HS256 (v2 legacy tokens)
    try:
        return jwt.decode(token, QR_SIGNING_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def is_jwt_qr(data: str) -> bool:
    """Check if QR data is JWT format (v2/v3) vs legacy pipe-delimited (v1).

    JWT tokens have exactly 2 dots (header.payload.signature) and
    never contain pipe characters.
    """
    return data.count(".") == 2 and "|" not in data


def get_signing_key_for_event(event_id: str) -> str:
    """Get the public key PEM for offline QR verification.

    Returns the RS256 public key which is safe to distribute to any
    authenticated scanner app. Unlike HS256 secrets, public keys
    cannot be used to forge signatures.

    Args:
        event_id: The event to get the public key for.

    Returns:
        PEM-encoded RSA public key string.
    """
    return get_public_key_for_event(event_id)
