# app/services/offer_reservation_service.py
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from redis import Redis

logger = logging.getLogger(__name__)


class OfferReservationService:
    """
    Service for managing offer inventory reservations using Redis.

    Reservations are stored with TTL (Time To Live) to automatically
    release inventory if checkout is not completed.
    """

    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.reservation_ttl = 900  # 15 minutes in seconds

    def create_reservation(
        self,
        *,
        checkout_session_id: str,
        offer_id: str,
        quantity: int,
        user_id: str
    ) -> bool:
        """
        Create a reservation for offer inventory.

        Args:
            checkout_session_id: Stripe checkout session ID
            offer_id: Offer ID
            quantity: Quantity reserved
            user_id: User making the reservation

        Returns: True if reservation created, False otherwise
        """
        try:
            key = f"offer_reservation:{checkout_session_id}:{offer_id}"

            reservation_data = {
                "offer_id": offer_id,
                "quantity": quantity,
                "user_id": user_id,
                "checkout_session_id": checkout_session_id,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(seconds=self.reservation_ttl)).isoformat()
            }

            # Store with TTL
            self.redis.setex(
                key,
                self.reservation_ttl,
                json.dumps(reservation_data)
            )

            logger.info(
                f"Created reservation for offer {offer_id}, "
                f"quantity {quantity}, session {checkout_session_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to create reservation: {str(e)}")
            return False

    def get_reservation(
        self,
        *,
        checkout_session_id: str,
        offer_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get reservation data.

        Returns: Reservation dict or None if not found/expired
        """
        try:
            key = f"offer_reservation:{checkout_session_id}:{offer_id}"
            data = self.redis.get(key)

            if data:
                return json.loads(data)

            return None

        except Exception as e:
            logger.error(f"Failed to get reservation: {str(e)}")
            return None

    def release_reservation(
        self,
        *,
        checkout_session_id: str,
        offer_id: str
    ) -> bool:
        """
        Manually release a reservation (e.g., when checkout is cancelled).

        Returns: True if released, False otherwise
        """
        try:
            key = f"offer_reservation:{checkout_session_id}:{offer_id}"
            deleted = self.redis.delete(key)

            if deleted:
                logger.info(
                    f"Released reservation for offer {offer_id}, "
                    f"session {checkout_session_id}"
                )

            return bool(deleted)

        except Exception as e:
            logger.error(f"Failed to release reservation: {str(e)}")
            return False

    def confirm_reservation(
        self,
        *,
        checkout_session_id: str,
        offer_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Confirm a reservation (payment succeeded).
        Returns reservation data and deletes it from Redis.

        Returns: Reservation dict or None if not found
        """
        try:
            # Get the reservation data
            reservation = self.get_reservation(
                checkout_session_id=checkout_session_id,
                offer_id=offer_id
            )

            if reservation:
                # Delete from Redis
                self.release_reservation(
                    checkout_session_id=checkout_session_id,
                    offer_id=offer_id
                )

                logger.info(
                    f"Confirmed reservation for offer {offer_id}, "
                    f"session {checkout_session_id}"
                )

            return reservation

        except Exception as e:
            logger.error(f"Failed to confirm reservation: {str(e)}")
            return None

    def get_user_active_reservations(self, user_id: str) -> list[Dict[str, Any]]:
        """
        Get all active reservations for a user.

        Note: This is a scan operation and should be used sparingly.
        """
        try:
            reservations = []
            pattern = f"offer_reservation:*"

            # Scan for all reservation keys
            for key in self.redis.scan_iter(match=pattern):
                data = self.redis.get(key)
                if data:
                    reservation = json.loads(data)
                    if reservation.get("user_id") == user_id:
                        reservations.append(reservation)

            return reservations

        except Exception as e:
            logger.error(f"Failed to get user reservations: {str(e)}")
            return []

    def cleanup_expired_reservations(self) -> int:
        """
        Background task: Find and cleanup expired reservations.

        Note: Redis TTL handles this automatically, but this method
        can be used to manually trigger cleanup if needed.

        Returns: Number of reservations cleaned up
        """
        # Redis handles TTL automatically, so this is mostly for monitoring
        try:
            pattern = f"offer_reservation:*"
            count = 0

            for key in self.redis.scan_iter(match=pattern):
                ttl = self.redis.ttl(key)

                # If TTL is -1 (no expiration) or -2 (key doesn't exist), clean it up
                if ttl in [-1, -2]:
                    self.redis.delete(key)
                    count += 1

            if count > 0:
                logger.info(f"Cleaned up {count} expired reservations")

            return count

        except Exception as e:
            logger.error(f"Failed to cleanup expired reservations: {str(e)}")
            return 0

    def extend_reservation(
        self,
        *,
        checkout_session_id: str,
        offer_id: str,
        additional_seconds: int = 300
    ) -> bool:
        """
        Extend a reservation TTL (e.g., if user needs more time).

        Args:
            checkout_session_id: Stripe checkout session ID
            offer_id: Offer ID
            additional_seconds: Additional time in seconds (default: 5 minutes)

        Returns: True if extended, False otherwise
        """
        try:
            key = f"offer_reservation:{checkout_session_id}:{offer_id}"
            current_ttl = self.redis.ttl(key)

            if current_ttl > 0:
                new_ttl = current_ttl + additional_seconds
                self.redis.expire(key, new_ttl)

                logger.info(
                    f"Extended reservation for offer {offer_id}, "
                    f"session {checkout_session_id} by {additional_seconds}s"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to extend reservation: {str(e)}")
            return False


def get_reservation_service(redis_client: Redis) -> OfferReservationService:
    """Factory function to create reservation service."""
    return OfferReservationService(redis_client)


# Initialize Redis client and create singleton instance
try:
    from app.core.config import settings
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    offer_reservation_service = OfferReservationService(redis_client)
except Exception as e:
    logger.warning(f"Failed to initialize Redis client for offer reservations: {str(e)}")
    # Create a dummy instance that will fail gracefully
    offer_reservation_service = None
