# app/services/payment/providers/stripe_provider.py
import stripe
import time
import logging
from typing import Optional, Dict, Any, Set
from datetime import datetime, timezone
from dataclasses import dataclass

from ..provider_interface import (
    PaymentProviderInterface,
    CreatePaymentIntentParams,
    PaymentIntentResult,
    PaymentIntentStatus,
    PaymentIntentStatusEnum,
    CreateRefundParams,
    RefundResult,
    RefundStatusEnum,
    PaymentDetails,
    WebhookEvent,
    WebhookEventType,
    PaymentFeature,
    HealthCheckResult,
    RefundReason,
)

logger = logging.getLogger(__name__)


@dataclass
class StripeConfig:
    """Configuration for Stripe provider."""
    secret_key: str
    publishable_key: str
    webhook_secret: str
    api_version: str = "2023-10-16"
    max_retries: int = 2


# Mapping from Stripe payment intent status to our standardized status
STRIPE_STATUS_MAP: Dict[str, PaymentIntentStatusEnum] = {
    "requires_payment_method": PaymentIntentStatusEnum.REQUIRES_PAYMENT_METHOD,
    "requires_confirmation": PaymentIntentStatusEnum.REQUIRES_CONFIRMATION,
    "requires_action": PaymentIntentStatusEnum.REQUIRES_ACTION,
    "processing": PaymentIntentStatusEnum.PROCESSING,
    "succeeded": PaymentIntentStatusEnum.SUCCEEDED,
    "canceled": PaymentIntentStatusEnum.CANCELLED,
    "requires_capture": PaymentIntentStatusEnum.SUCCEEDED,  # For manual capture
}

# Mapping from Stripe event types to our standardized event types
STRIPE_EVENT_MAP: Dict[str, WebhookEventType] = {
    "payment_intent.created": WebhookEventType.PAYMENT_INTENT_CREATED,
    "payment_intent.succeeded": WebhookEventType.PAYMENT_INTENT_SUCCEEDED,
    "payment_intent.payment_failed": WebhookEventType.PAYMENT_INTENT_FAILED,
    "payment_intent.canceled": WebhookEventType.PAYMENT_INTENT_CANCELLED,
    "charge.succeeded": WebhookEventType.CHARGE_SUCCEEDED,
    "charge.failed": WebhookEventType.CHARGE_FAILED,
    "charge.refunded": WebhookEventType.CHARGE_REFUNDED,
    "refund.created": WebhookEventType.REFUND_CREATED,
    "refund.updated": WebhookEventType.REFUND_SUCCEEDED,
    "refund.failed": WebhookEventType.REFUND_FAILED,
}

# Mapping from our refund reasons to Stripe refund reasons
REFUND_REASON_MAP: Dict[RefundReason, str] = {
    RefundReason.REQUESTED_BY_CUSTOMER: "requested_by_customer",
    RefundReason.DUPLICATE: "duplicate",
    RefundReason.FRAUDULENT: "fraudulent",
    RefundReason.EVENT_CANCELLED: "requested_by_customer",  # Stripe doesn't have this
    RefundReason.OTHER: "requested_by_customer",  # Default
}

# Supported features for Stripe
STRIPE_FEATURES: Set[PaymentFeature] = {
    PaymentFeature.REFUNDS,
    PaymentFeature.PARTIAL_REFUNDS,
    PaymentFeature.RECURRING,
    PaymentFeature.SAVED_PAYMENT_METHODS,
    PaymentFeature.THREE_D_SECURE,
    PaymentFeature.WEBHOOKS,
    PaymentFeature.CONNECT_MARKETPLACE,
}


class StripeProvider(PaymentProviderInterface):
    """
    Stripe implementation of PaymentProviderInterface.

    SECURITY NOTES:
    - Never log full card details
    - Always verify webhook signatures
    - Use idempotency keys for all mutations
    - Handle rate limiting gracefully
    """

    def __init__(self, config: StripeConfig):
        """Initialize Stripe provider with configuration."""
        self._config = config
        self._publishable_key = config.publishable_key

        # Initialize Stripe with locked API version
        stripe.api_key = config.secret_key
        stripe.api_version = config.api_version
        stripe.max_network_retries = config.max_retries

    @property
    def code(self) -> str:
        return "stripe"

    @property
    def name(self) -> str:
        return "Stripe"

    def get_publishable_key(self) -> str:
        """Get the publishable key for client-side use."""
        return self._publishable_key

    async def create_payment_intent(
        self, params: CreatePaymentIntentParams
    ) -> PaymentIntentResult:
        """
        Create a Stripe PaymentIntent for checkout.

        Uses idempotency keys to ensure safe retries.
        """
        try:
            # Build the payment intent parameters
            intent_params: Dict[str, Any] = {
                "amount": params.amount,
                "currency": params.currency.lower(),
                "description": params.description,
                "receipt_email": params.customer_email,
                "metadata": {
                    **params.metadata,
                    "order_id": params.order_id,
                    "customer_name": params.customer_name,
                },
                "automatic_payment_methods": {
                    "enabled": True,
                },
            }

            # Set capture method
            if params.capture_method == "manual":
                intent_params["capture_method"] = "manual"

            # Handle Connect/marketplace model
            if params.connected_account_id:
                intent_params["transfer_data"] = {
                    "destination": params.connected_account_id,
                }
                if params.platform_fee_amount:
                    intent_params["application_fee_amount"] = params.platform_fee_amount

            # Create the payment intent with idempotency key
            intent = stripe.PaymentIntent.create(
                **intent_params,
                idempotency_key=params.idempotency_key,
            )

            # Map status
            status = STRIPE_STATUS_MAP.get(
                intent.status, PaymentIntentStatusEnum.REQUIRES_PAYMENT_METHOD
            )

            return PaymentIntentResult(
                intent_id=intent.id,
                client_secret=intent.client_secret,
                status=status,
                expires_at=None,  # Stripe intents don't expire by default
                provider_metadata={
                    "livemode": intent.livemode,
                    "payment_method_types": intent.payment_method_types,
                },
            )

        except stripe.error.CardError as e:
            logger.error(f"Card error creating payment intent: {e.user_message}")
            raise PaymentError(
                code="CARD_ERROR",
                message=e.user_message or "Card was declined",
                retryable=True,
            )
        except stripe.error.RateLimitError as e:
            logger.error(f"Rate limit error: {e}")
            raise PaymentError(
                code="RATE_LIMIT",
                message="Too many requests. Please try again.",
                retryable=True,
            )
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid request error: {e}")
            raise PaymentError(
                code="INVALID_REQUEST",
                message=str(e),
                retryable=False,
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {e}")
            raise PaymentError(
                code="PROVIDER_ERROR",
                message="Payment service temporarily unavailable",
                retryable=True,
            )

    async def get_payment_intent(self, intent_id: str) -> PaymentIntentStatus:
        """Retrieve current status of a payment intent."""
        try:
            intent = stripe.PaymentIntent.retrieve(intent_id)

            # Get payment method details if available
            payment_method_type = None
            payment_method_details = None

            if intent.payment_method:
                try:
                    pm = stripe.PaymentMethod.retrieve(intent.payment_method)
                    payment_method_type = pm.type
                    if pm.type == "card" and pm.card:
                        payment_method_details = {
                            "brand": pm.card.brand,
                            "last4": pm.card.last4,
                            "exp_month": pm.card.exp_month,
                            "exp_year": pm.card.exp_year,
                        }
                except stripe.error.StripeError:
                    pass  # Payment method details are optional

            # Get failure info if applicable
            failure_code = None
            failure_message = None
            if intent.last_payment_error:
                failure_code = intent.last_payment_error.code
                failure_message = intent.last_payment_error.message

            status = STRIPE_STATUS_MAP.get(
                intent.status, PaymentIntentStatusEnum.FAILED
            )

            return PaymentIntentStatus(
                intent_id=intent.id,
                status=status,
                amount=intent.amount,
                currency=intent.currency.upper(),
                payment_method_type=payment_method_type,
                payment_method_details=payment_method_details,
                failure_code=failure_code,
                failure_message=failure_message,
            )

        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving payment intent {intent_id}: {e}")
            raise PaymentError(
                code="PROVIDER_ERROR",
                message="Could not retrieve payment status",
                retryable=True,
            )

    async def cancel_payment_intent(self, intent_id: str) -> None:
        """Cancel a pending payment intent."""
        try:
            stripe.PaymentIntent.cancel(intent_id)
        except stripe.error.InvalidRequestError as e:
            # Intent might already be cancelled or completed
            if "cannot be canceled" not in str(e).lower():
                raise PaymentError(
                    code="CANCEL_FAILED",
                    message=str(e),
                    retryable=False,
                )
        except stripe.error.StripeError as e:
            logger.error(f"Error cancelling payment intent {intent_id}: {e}")
            raise PaymentError(
                code="PROVIDER_ERROR",
                message="Could not cancel payment",
                retryable=True,
            )

    async def create_refund(self, params: CreateRefundParams) -> RefundResult:
        """Process a refund for a completed payment."""
        try:
            refund_params: Dict[str, Any] = {
                "payment_intent": params.payment_id,
                "reason": REFUND_REASON_MAP.get(params.reason, "requested_by_customer"),
            }

            # Partial refund
            if params.amount:
                refund_params["amount"] = params.amount

            # Add metadata
            if params.metadata:
                refund_params["metadata"] = params.metadata

            refund = stripe.Refund.create(
                **refund_params,
                idempotency_key=params.idempotency_key,
            )

            # Map status
            status_map = {
                "succeeded": RefundStatusEnum.SUCCEEDED,
                "pending": RefundStatusEnum.PENDING,
                "failed": RefundStatusEnum.FAILED,
                "canceled": RefundStatusEnum.CANCELLED,
            }
            status = status_map.get(refund.status, RefundStatusEnum.PENDING)

            return RefundResult(
                refund_id=refund.id,
                status=status,
                amount=refund.amount,
                currency=refund.currency.upper(),
                provider_metadata={
                    "charge_id": refund.charge,
                    "reason": refund.reason,
                },
            )

        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid refund request: {e}")
            raise PaymentError(
                code="INVALID_REFUND",
                message=str(e),
                retryable=False,
            )
        except stripe.error.StripeError as e:
            logger.error(f"Error creating refund: {e}")
            raise PaymentError(
                code="PROVIDER_ERROR",
                message="Could not process refund",
                retryable=True,
            )

    async def get_payment(self, payment_id: str) -> PaymentDetails:
        """Get details of a specific payment (charge or payment intent)."""
        try:
            # Try to get as payment intent first
            if payment_id.startswith("pi_"):
                intent = stripe.PaymentIntent.retrieve(
                    payment_id,
                    expand=["charges", "payment_method"],
                )

                # Get charge details
                charge = intent.charges.data[0] if intent.charges.data else None
                amount_refunded = charge.amount_refunded if charge else 0

                # Get payment method details
                payment_method_type = None
                payment_method_details = None
                if intent.payment_method:
                    pm = intent.payment_method
                    if hasattr(pm, "type"):
                        payment_method_type = pm.type
                        if pm.type == "card" and hasattr(pm, "card"):
                            payment_method_details = {
                                "brand": pm.card.brand,
                                "last4": pm.card.last4,
                                "exp_month": pm.card.exp_month,
                                "exp_year": pm.card.exp_year,
                            }

                return PaymentDetails(
                    payment_id=intent.id,
                    intent_id=intent.id,
                    status=intent.status,
                    amount=intent.amount,
                    currency=intent.currency.upper(),
                    amount_refunded=amount_refunded,
                    payment_method_type=payment_method_type,
                    payment_method_details=payment_method_details,
                    created_at=datetime.fromtimestamp(intent.created, tz=timezone.utc),
                    provider_metadata={
                        "livemode": intent.livemode,
                        "charge_id": charge.id if charge else None,
                    },
                )
            else:
                # Get as charge
                charge = stripe.Charge.retrieve(payment_id)

                return PaymentDetails(
                    payment_id=charge.id,
                    intent_id=charge.payment_intent,
                    status=charge.status,
                    amount=charge.amount,
                    currency=charge.currency.upper(),
                    amount_refunded=charge.amount_refunded,
                    payment_method_type=charge.payment_method_details.type if charge.payment_method_details else None,
                    payment_method_details=None,
                    created_at=datetime.fromtimestamp(charge.created, tz=timezone.utc),
                    provider_metadata={
                        "livemode": charge.livemode,
                    },
                )

        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving payment {payment_id}: {e}")
            raise PaymentError(
                code="PROVIDER_ERROR",
                message="Could not retrieve payment details",
                retryable=True,
            )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Stripe webhook signature."""
        try:
            stripe.Webhook.construct_event(
                payload,
                signature,
                self._config.webhook_secret,
            )
            return True
        except stripe.error.SignatureVerificationError:
            return False
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False

    def parse_webhook_event(self, payload: bytes) -> WebhookEvent:
        """Parse Stripe webhook event into standardized format."""
        try:
            event = stripe.Event.construct_from(
                stripe.util.convert_to_dict(
                    stripe.util.json.loads(payload.decode("utf-8"))
                ),
                stripe.api_key,
            )

            # Map event type
            event_type = STRIPE_EVENT_MAP.get(
                event.type, WebhookEventType.UNKNOWN
            )

            # Extract relevant data
            data_object = event.data.object
            data: Dict[str, Any] = {
                "status": getattr(data_object, "status", None),
            }

            # Payment intent events
            if hasattr(data_object, "id"):
                if data_object.id.startswith("pi_"):
                    data["paymentIntentId"] = data_object.id
                    data["amount"] = getattr(data_object, "amount", None)
                    data["currency"] = getattr(data_object, "currency", "").upper()
                    data["metadata"] = getattr(data_object, "metadata", {})
                elif data_object.id.startswith("ch_"):
                    data["paymentId"] = data_object.id
                    data["paymentIntentId"] = getattr(data_object, "payment_intent", None)
                    data["amount"] = getattr(data_object, "amount", None)
                    data["currency"] = getattr(data_object, "currency", "").upper()
                elif data_object.id.startswith("re_"):
                    data["refundId"] = data_object.id
                    data["paymentIntentId"] = getattr(data_object, "payment_intent", None)
                    data["amount"] = getattr(data_object, "amount", None)
                    data["currency"] = getattr(data_object, "currency", "").upper()

            # Failure info
            if hasattr(data_object, "last_payment_error") and data_object.last_payment_error:
                data["failureCode"] = data_object.last_payment_error.code
                data["failureMessage"] = data_object.last_payment_error.message

            return WebhookEvent(
                event_id=event.id,
                event_type=event_type,
                data=data,
                created_at=datetime.fromtimestamp(event.created, tz=timezone.utc),
                raw_payload=event,
            )

        except Exception as e:
            logger.error(f"Error parsing webhook event: {e}")
            raise PaymentError(
                code="PARSE_ERROR",
                message="Could not parse webhook event",
                retryable=False,
            )

    def supports_feature(self, feature: PaymentFeature) -> bool:
        """Check if Stripe supports a specific feature."""
        return feature in STRIPE_FEATURES

    async def health_check(self) -> HealthCheckResult:
        """Health check for Stripe API."""
        try:
            start_time = time.time()
            # Simple balance retrieval to check API connectivity
            stripe.Balance.retrieve()
            latency_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                healthy=True,
                latency_ms=latency_ms,
                message="Stripe API is healthy",
            )
        except stripe.error.AuthenticationError:
            return HealthCheckResult(
                healthy=False,
                latency_ms=0,
                message="Invalid Stripe API key",
            )
        except stripe.error.StripeError as e:
            return HealthCheckResult(
                healthy=False,
                latency_ms=0,
                message=f"Stripe API error: {str(e)}",
            )


class PaymentError(Exception):
    """Custom exception for payment errors."""

    def __init__(self, code: str, message: str, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)
