# app/services/offer_stripe_service.py
import stripe
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)


class OfferStripeService:
    """Service for Stripe operations related to offers."""

    def __init__(self):
        """Initialize Stripe API key."""
        if not stripe.api_key:
            if not settings.STRIPE_SECRET_KEY:
                logger.error("STRIPE_SECRET_KEY not configured")
                raise ValueError("Stripe API key not configured")
            stripe.api_key = settings.STRIPE_SECRET_KEY
            logger.info("Stripe API initialized for offer service")

    @staticmethod
    def create_product(
        *,
        offer_id: str,
        title: str,
        description: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a Stripe Product for an offer.

        Returns: stripe_product_id or None if error
        """
        try:
            product_data = {
                "name": title,
                "metadata": {
                    "offer_id": offer_id,
                    "source": "offer"
                }
            }

            if description:
                product_data["description"] = description

            if image_url:
                product_data["images"] = [image_url]

            product = stripe.Product.create(**product_data)

            logger.info(f"Created Stripe product {product.id} for offer {offer_id}")
            return product.id

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to create Stripe product",
                extra={
                    "offer_id": offer_id,
                    "title": title,
                    "error_type": type(e).__name__,
                    "error": str(e)
                },
                exc_info=True
            )
            return None

    @staticmethod
    def create_price(
        *,
        product_id: str,
        price: float,
        currency: str = "USD",
        offer_id: str
    ) -> Optional[str]:
        """
        Create a Stripe Price for a product.

        Args:
            product_id: Stripe product ID
            price: Price in currency units (e.g., 99.99)
            currency: Currency code (e.g., USD)
            offer_id: Offer ID for metadata

        Returns: stripe_price_id or None if error
        """
        try:
            # Convert price to cents (Stripe uses smallest currency unit)
            unit_amount = int(price * 100)

            price_obj = stripe.Price.create(
                product=product_id,
                unit_amount=unit_amount,
                currency=currency.lower(),
                metadata={
                    "offer_id": offer_id
                }
            )

            logger.info(f"Created Stripe price {price_obj.id} for offer {offer_id}")
            return price_obj.id

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe price for offer {offer_id}: {str(e)}")
            return None

    @staticmethod
    def create_checkout_session(
        *,
        price_id: str,
        quantity: int,
        success_url: str,
        cancel_url: str,
        customer_email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a Stripe Checkout Session for offer purchase.

        Returns: Dict with session_id and url, or None if error
        """
        try:
            session_data = {
                "payment_method_types": ["card"],
                "line_items": [{
                    "price": price_id,
                    "quantity": quantity,
                }],
                "mode": "payment",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": metadata or {},
                "expires_at": int((datetime.utcnow() + timedelta(minutes=30)).timestamp()),
            }

            if customer_email:
                session_data["customer_email"] = customer_email

            session = stripe.checkout.Session.create(**session_data)

            logger.info(f"Created Stripe checkout session {session.id}")

            return {
                "session_id": session.id,
                "url": session.url
            }

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to create Stripe checkout session",
                extra={
                    "price_id": price_id,
                    "quantity": quantity,
                    "metadata": metadata,
                    "error_type": type(e).__name__,
                    "error": str(e)
                },
                exc_info=True
            )
            return None

    @staticmethod
    def get_checkout_session(session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a Stripe Checkout Session.

        Returns: Session data or None if error
        """
        try:
            session = stripe.checkout.Session.retrieve(session_id)

            return {
                "id": session.id,
                "status": session.status,
                "payment_status": session.payment_status,
                "customer_email": session.customer_email,
                "metadata": session.metadata,
                "amount_total": session.amount_total / 100 if session.amount_total else 0,
                "currency": session.currency
            }

        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve Stripe session {session_id}: {str(e)}")
            return None

    @staticmethod
    def update_product(
        *,
        product_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> bool:
        """
        Update a Stripe Product.

        Returns: True if successful, False otherwise
        """
        try:
            update_data = {}

            if name:
                update_data["name"] = name

            if description:
                update_data["description"] = description

            if image_url:
                update_data["images"] = [image_url]

            if update_data:
                stripe.Product.modify(product_id, **update_data)
                logger.info(f"Updated Stripe product {product_id}")
                return True

            return True

        except stripe.error.StripeError as e:
            logger.error(f"Failed to update Stripe product {product_id}: {str(e)}")
            return False

    @staticmethod
    def archive_product(product_id: str) -> bool:
        """
        Archive a Stripe Product.

        Returns: True if successful, False otherwise
        """
        try:
            stripe.Product.modify(
                product_id,
                active=False
            )
            logger.info(f"Archived Stripe product {product_id}")
            return True

        except stripe.error.StripeError as e:
            logger.error(f"Failed to archive Stripe product {product_id}: {str(e)}")
            return False


# Create singleton instance
offer_stripe_service = OfferStripeService()
