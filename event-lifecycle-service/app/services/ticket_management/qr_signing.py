"""
JWT-based QR code signing for offline-verifiable tickets.

Replaces the old SHA256(plaintext)[:8] checksum which was guessable and forgeable.
Uses HMAC-SHA256 with a server-side secret for cryptographic signing.

QR format versions:
  v1 (legacy): pipe-delimited "{id}|{code}|{event_id}|{sha256_hash[:8]}"
  v2 (current): JWT signed with HS256 containing ticket claims

For future offline verification, upgrade to RS256 with public/private keys
so scanner apps can verify without calling the server. Starting with HS256
for server-side verification.
"""

import jwt
import os
from datetime import datetime, timezone, timedelta
from typing import Optional


# Use a dedicated secret for QR signing, separate from the main JWT_SECRET.
# This limits blast radius if one secret is compromised.
QR_SIGNING_SECRET = os.environ.get(
    "QR_SIGNING_SECRET",
    "CHANGE-ME-IN-PRODUCTION-use-a-64-char-random-string",
)


def sign_ticket_qr(
    ticket_id: str,
    ticket_code: str,
    event_id: str,
    user_id: Optional[str],
    attendee_name: str,
    event_end_date: Optional[datetime] = None,
) -> str:
    """Generate a signed JWT for embedding in a QR code.

    The JWT contains all claims needed for verification:
    - tid: ticket ID (primary key)
    - tcode: human-readable ticket code (TKT-XXXXXX-XX)
    - eid: event ID the ticket belongs to
    - sub: user ID of ticket owner (nullable for guest tickets)
    - name: attendee name for display on scanner UI
    - iat: issued-at timestamp
    - exp: expiration (24h after event end, or 30 days if no end date)
    - v: QR format version (2 = JWT, 1 = legacy pipe-delimited)

    Returns:
        Compact JWT string suitable for QR code encoding.
    """
    now = datetime.now(timezone.utc)

    # Expire 24 hours after event ends, or 30 days from now if no end date
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
        "v": 2,
    }

    return jwt.encode(payload, QR_SIGNING_SECRET, algorithm="HS256")


def verify_ticket_qr(token: str) -> Optional[dict]:
    """Verify a signed QR token and return decoded claims.

    Returns:
        Decoded JWT payload dict if valid, or None if:
        - Token has expired (ExpiredSignatureError)
        - Signature is invalid / tampered (InvalidTokenError)
        - Token is malformed
    """
    try:
        return jwt.decode(token, QR_SIGNING_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def is_jwt_qr(data: str) -> bool:
    """Check if QR data is JWT format (v2) vs legacy pipe-delimited (v1).

    JWT tokens have exactly 2 dots (header.payload.signature) and
    never contain pipe characters. Legacy format uses pipes as delimiters.
    """
    return data.count(".") == 2 and "|" not in data


def get_signing_key_for_event(event_id: str) -> str:
    """Get the HMAC signing key for offline QR verification.

    Currently returns the global QR_SIGNING_SECRET for all events.
    In production, this could be upgraded to per-event keys stored in
    a key management service, or to RS256 with per-event key pairs
    so that the public key can be safely distributed to scanner apps.

    IMPORTANT: This returns a secret key (HMAC). The endpoint serving
    this must be protected with organizer-level authentication.
    When upgraded to RS256, only the public key would be returned and
    the endpoint could be less restricted.

    Args:
        event_id: The event ID (reserved for future per-event key support).

    Returns:
        The HMAC signing key string.
    """
    return QR_SIGNING_SECRET
