# app/services/payment/provider_interface.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class PaymentIntentStatusEnum(str, Enum):
    """Standardized payment intent status."""
    REQUIRES_PAYMENT_METHOD = "requires_payment_method"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REQUIRES_ACTION = "requires_action"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"
    FAILED = "failed"


class RefundStatusEnum(str, Enum):
    """Standardized refund status."""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WebhookEventType(str, Enum):
    """Standardized webhook event types."""
    PAYMENT_INTENT_CREATED = "payment_intent.created"
    PAYMENT_INTENT_SUCCEEDED = "payment_intent.succeeded"
    PAYMENT_INTENT_FAILED = "payment_intent.failed"
    PAYMENT_INTENT_CANCELLED = "payment_intent.cancelled"
    CHARGE_SUCCEEDED = "charge.succeeded"
    CHARGE_FAILED = "charge.failed"
    CHARGE_REFUNDED = "charge.refunded"
    REFUND_CREATED = "refund.created"
    REFUND_SUCCEEDED = "refund.succeeded"
    REFUND_FAILED = "refund.failed"
    UNKNOWN = "unknown"


class PaymentFeature(str, Enum):
    """Available payment features."""
    REFUNDS = "refunds"
    PARTIAL_REFUNDS = "partial_refunds"
    RECURRING = "recurring"
    SAVED_PAYMENT_METHODS = "saved_payment_methods"
    THREE_D_SECURE = "3d_secure"
    BANK_TRANSFER = "bank_transfer"
    MOBILE_MONEY = "mobile_money"
    WEBHOOKS = "webhooks"
    CONNECT_MARKETPLACE = "connect_marketplace"


class RefundReason(str, Enum):
    """Refund reasons."""
    REQUESTED_BY_CUSTOMER = "requested_by_customer"
    DUPLICATE = "duplicate"
    FRAUDULENT = "fraudulent"
    EVENT_CANCELLED = "event_cancelled"
    OTHER = "other"


@dataclass
class CreatePaymentIntentParams:
    """Parameters for creating a payment intent."""
    order_id: str
    amount: int  # In smallest currency unit (cents)
    currency: str  # ISO 4217
    customer_email: str
    customer_name: str
    description: str
    metadata: Dict[str, str]
    idempotency_key: str
    customer_id: Optional[str] = None
    connected_account_id: Optional[str] = None
    platform_fee_amount: Optional[int] = None
    allowed_payment_methods: Optional[List[str]] = None
    capture_method: str = "automatic"
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@dataclass
class PaymentIntentResult:
    """Result of creating a payment intent."""
    intent_id: str
    client_secret: str
    status: PaymentIntentStatusEnum
    expires_at: Optional[datetime] = None
    provider_metadata: Optional[Dict[str, Any]] = None


@dataclass
class PaymentIntentStatus:
    """Current status of a payment intent."""
    intent_id: str
    status: PaymentIntentStatusEnum
    amount: int
    currency: str
    payment_method_type: Optional[str] = None
    payment_method_details: Optional[Dict[str, Any]] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None


@dataclass
class CreateRefundParams:
    """Parameters for creating a refund."""
    payment_id: str  # Provider's payment/charge ID
    idempotency_key: str
    amount: Optional[int] = None  # Optional for partial refund (in cents)
    reason: RefundReason = RefundReason.REQUESTED_BY_CUSTOMER
    metadata: Optional[Dict[str, str]] = None
    refund_application_fee: Optional[bool] = None  # For Connect: refund the platform's application fee


@dataclass
class RefundResult:
    """Result of a refund operation."""
    refund_id: str
    status: RefundStatusEnum
    amount: int
    currency: str
    provider_metadata: Optional[Dict[str, Any]] = None


@dataclass
class PaymentDetails:
    """Details of a specific payment."""
    payment_id: str
    intent_id: Optional[str]
    status: str
    amount: int
    currency: str
    amount_refunded: int
    payment_method_type: Optional[str]
    payment_method_details: Optional[Dict[str, Any]]
    created_at: datetime
    provider_metadata: Optional[Dict[str, Any]] = None


@dataclass
class WebhookEvent:
    """Standardized webhook event."""
    event_id: str
    event_type: WebhookEventType
    data: Dict[str, Any]
    created_at: datetime
    raw_payload: Any


@dataclass
class HealthCheckResult:
    """Health check result."""
    healthy: bool
    latency_ms: float
    message: Optional[str] = None


class PaymentProviderInterface(ABC):
    """
    Core interface that all payment providers must implement.
    This abstraction allows swapping providers without changing business logic.
    """

    @property
    @abstractmethod
    def code(self) -> str:
        """Provider code identifier (e.g., 'stripe', 'paystack')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g., 'Stripe', 'Paystack')."""
        pass

    @abstractmethod
    async def create_payment_intent(
        self, params: CreatePaymentIntentParams
    ) -> PaymentIntentResult:
        """
        Initialize a payment intent/session for checkout.
        Returns a client-side token for secure payment form.
        """
        pass

    @abstractmethod
    async def get_payment_intent(self, intent_id: str) -> PaymentIntentStatus:
        """Retrieve current status of a payment intent."""
        pass

    @abstractmethod
    async def cancel_payment_intent(self, intent_id: str) -> None:
        """Cancel a pending payment intent."""
        pass

    @abstractmethod
    async def create_refund(self, params: CreateRefundParams) -> RefundResult:
        """Process a refund for a completed payment."""
        pass

    @abstractmethod
    async def get_payment(self, payment_id: str) -> PaymentDetails:
        """Get details of a specific payment."""
        pass

    @abstractmethod
    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> bool:
        """Verify webhook signature."""
        pass

    @abstractmethod
    def parse_webhook_event(self, payload: bytes) -> WebhookEvent:
        """Parse webhook event into standardized format."""
        pass

    @abstractmethod
    def supports_feature(self, feature: PaymentFeature) -> bool:
        """Check if provider supports a specific feature."""
        pass

    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        """Health check for the provider."""
        pass

    def get_publishable_key(self) -> str:
        """Get the publishable/public API key for client-side use."""
        raise NotImplementedError("Provider does not support publishable keys")
