# app/schemas/payment.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================
# Enums
# ============================================

class OrderStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    cancelled = "cancelled"
    refunded = "refunded"
    partially_refunded = "partially_refunded"
    expired = "expired"


class PaymentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    refunded = "refunded"
    partially_refunded = "partially_refunded"


class RefundStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class RefundReason(str, Enum):
    requested_by_customer = "requested_by_customer"
    duplicate = "duplicate"
    fraudulent = "fraudulent"
    event_cancelled = "event_cancelled"
    other = "other"


class DiscountType(str, Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class WebhookEventStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    processed = "processed"
    failed = "failed"
    skipped = "skipped"


# ============================================
# Money Type
# ============================================

class Money(BaseModel):
    amount: int = Field(..., description="Amount in smallest currency unit (cents)")
    currency: str = Field(..., max_length=3, description="ISO 4217 currency code")

    @property
    def formatted(self) -> str:
        """Format amount as currency string."""
        symbols = {"USD": "$", "EUR": "€", "GBP": "£", "CAD": "C$", "AUD": "A$"}
        symbol = symbols.get(self.currency.upper(), self.currency + " ")
        return f"{symbol}{self.amount / 100:.2f}"

    model_config = {"from_attributes": True}


# ============================================
# Payment Provider Schemas
# ============================================

class PaymentProviderBase(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    is_active: bool = True
    is_default: bool = False
    supported_currencies: List[str] = []
    supported_countries: List[str] = []
    supported_features: Optional[Dict[str, Any]] = {}
    config: Optional[Dict[str, Any]] = {}


class PaymentProviderCreate(PaymentProviderBase):
    pass


class PaymentProvider(PaymentProviderBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================
# Organization Payment Settings Schemas
# ============================================

class OrganizationPaymentSettingsBase(BaseModel):
    provider_id: str
    connected_account_id: Optional[str] = None
    payout_schedule: Optional[str] = "automatic"
    payout_currency: Optional[str] = "USD"
    platform_fee_percent: Optional[float] = 0.0
    platform_fee_fixed: Optional[int] = 0
    is_active: bool = True


class OrganizationPaymentSettingsCreate(OrganizationPaymentSettingsBase):
    pass


class OrganizationPaymentSettingsUpdate(BaseModel):
    connected_account_id: Optional[str] = None
    payout_schedule: Optional[str] = None
    payout_currency: Optional[str] = None
    platform_fee_percent: Optional[float] = None
    platform_fee_fixed: Optional[int] = None
    is_active: Optional[bool] = None


class OrganizationPaymentSettings(OrganizationPaymentSettingsBase):
    id: str
    organization_id: str
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================
# Ticket Type Schemas
# ============================================

class TicketTypeBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    price: int = Field(0, ge=0, description="Price in cents")
    currency: str = Field("USD", max_length=3)
    quantity_total: Optional[int] = Field(None, ge=0, description="None = unlimited")
    min_per_order: int = Field(1, ge=1)
    max_per_order: int = Field(10, ge=1)
    sales_start_at: Optional[datetime] = None
    sales_end_at: Optional[datetime] = None
    is_active: bool = True
    is_hidden: bool = False
    sort_order: int = 0


class TicketTypeCreate(TicketTypeBase):
    event_id: str


class TicketTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    currency: Optional[str] = None
    quantity_total: Optional[int] = None
    min_per_order: Optional[int] = None
    max_per_order: Optional[int] = None
    sales_start_at: Optional[datetime] = None
    sales_end_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    is_hidden: Optional[bool] = None
    sort_order: Optional[int] = None


class TicketType(TicketTypeBase):
    id: str
    event_id: str
    quantity_sold: int = 0
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime

    @property
    def quantity_available(self) -> Optional[int]:
        if self.quantity_total is None:
            return None
        return max(0, self.quantity_total - self.quantity_sold)

    @property
    def is_sold_out(self) -> bool:
        if self.quantity_total is None:
            return False
        return self.quantity_sold >= self.quantity_total

    model_config = {"from_attributes": True}


# ============================================
# Promo Code Schemas
# ============================================

class PromoCodeBase(BaseModel):
    code: str = Field(..., max_length=50)
    description: Optional[str] = None
    discount_type: DiscountType
    discount_value: int = Field(..., ge=0)
    currency: Optional[str] = "USD"
    applicable_ticket_type_ids: Optional[List[str]] = None
    max_uses: Optional[int] = None
    max_uses_per_user: int = 1
    minimum_order_amount: Optional[int] = None  # In cents
    minimum_tickets: Optional[int] = None
    min_order_amount: Optional[int] = None  # Legacy
    max_discount_amount: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: bool = True


class PromoCodeCreate(PromoCodeBase):
    event_id: Optional[str] = None

    @field_validator("discount_value")
    @classmethod
    def validate_discount_value(cls, v, info):
        discount_type = info.data.get("discount_type")
        if discount_type == DiscountType.PERCENTAGE and v > 100:
            raise ValueError("Percentage discount cannot exceed 100")
        return v


class PromoCodeUpdate(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None
    discount_type: Optional[DiscountType] = None
    discount_value: Optional[int] = None
    applicable_ticket_type_ids: Optional[List[str]] = None
    max_uses: Optional[int] = None
    max_uses_per_user: Optional[int] = None
    minimum_order_amount: Optional[int] = None
    minimum_tickets: Optional[int] = None
    min_order_amount: Optional[int] = None  # Legacy
    max_discount_amount: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: Optional[bool] = None


class PromoCode(PromoCodeBase):
    id: str
    organization_id: str
    event_id: Optional[str] = None
    times_used: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================
# Order Item Schemas
# ============================================

class OrderItemBase(BaseModel):
    ticket_type_id: str
    quantity: int = Field(..., ge=1)


class OrderItemCreate(OrderItemBase):
    pass


class OrderItem(OrderItemBase):
    id: str
    order_id: str
    unit_price: int
    total_price: int
    ticket_type_name: str
    ticket_type_description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================
# Order Schemas
# ============================================

class OrderBase(BaseModel):
    event_id: str
    currency: str = Field(..., max_length=3)


class CreateOrderInput(BaseModel):
    event_id: str
    items: List[OrderItemCreate] = Field(..., min_length=1)
    promo_code: Optional[str] = None
    # Guest checkout fields
    guest_email: Optional[str] = None
    guest_first_name: Optional[str] = None
    guest_last_name: Optional[str] = None
    guest_phone: Optional[str] = None


class OrderCreate(OrderBase):
    user_id: Optional[str] = None
    guest_email: Optional[str] = None
    guest_first_name: Optional[str] = None
    guest_last_name: Optional[str] = None
    guest_phone: Optional[str] = None
    subtotal: int
    discount_amount: int = 0
    tax_amount: int = 0
    platform_fee: int = 0
    total_amount: int
    # Stripe Connect fee fields
    subtotal_amount: Optional[int] = None
    fee_absorption: Optional[str] = "absorb"
    fee_breakdown_json: Optional[Dict[str, Any]] = None
    connected_account_id: Optional[str] = None
    promo_code_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    payment_provider: Optional[str] = None
    payment_intent_id: Optional[str] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None


class Order(OrderBase):
    id: str
    order_number: str
    organization_id: str
    user_id: Optional[str] = None
    guest_email: Optional[str] = None
    guest_first_name: Optional[str] = None
    guest_last_name: Optional[str] = None
    guest_phone: Optional[str] = None
    status: OrderStatus
    subtotal: int
    discount_amount: int
    tax_amount: int
    platform_fee: int
    total_amount: int
    # Stripe Connect fee fields
    subtotal_amount: Optional[int] = None
    fee_absorption: Optional[str] = "absorb"
    fee_breakdown_json: Optional[Dict[str, Any]] = None
    connected_account_id: Optional[str] = None
    promo_code_id: Optional[str] = None
    payment_provider: Optional[str] = None
    payment_intent_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    order_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================
# Payment Schemas
# ============================================

class PaymentBase(BaseModel):
    provider_code: str = Field(..., max_length=50)
    currency: str = Field(..., max_length=3)
    amount: int = Field(..., ge=0)


class PaymentCreate(PaymentBase):
    order_id: str
    organization_id: str
    provider_payment_id: str
    provider_intent_id: Optional[str] = None
    status: PaymentStatus = PaymentStatus.pending
    net_amount: int
    payment_method_type: Optional[str] = None
    payment_method_details: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None


class PaymentUpdate(BaseModel):
    status: Optional[PaymentStatus] = None
    amount_refunded: Optional[int] = None
    provider_fee: Optional[int] = None
    net_amount: Optional[int] = None
    payment_method_type: Optional[str] = None
    payment_method_details: Optional[Dict[str, Any]] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None
    processed_at: Optional[datetime] = None
    provider_metadata: Optional[Dict[str, Any]] = None


class Payment(PaymentBase):
    id: str
    order_id: str
    organization_id: str
    provider_payment_id: str
    provider_intent_id: Optional[str] = None
    status: PaymentStatus
    amount_refunded: int = 0
    provider_fee: int = 0
    net_amount: int
    payment_method_type: Optional[str] = None
    payment_method_details: Optional[Dict[str, Any]] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    idempotency_key: Optional[str] = None
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None
    processed_at: Optional[datetime] = None
    provider_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================
# Refund Schemas
# ============================================

class InitiateRefundInput(BaseModel):
    order_id: str
    amount: Optional[int] = None  # Optional for full refund
    reason: RefundReason
    reason_details: Optional[str] = None


class RefundCreate(BaseModel):
    payment_id: str
    order_id: str
    organization_id: str
    provider_code: str
    amount: int
    currency: str
    reason: RefundReason
    reason_details: Optional[str] = None
    initiated_by_user_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class RefundUpdate(BaseModel):
    status: Optional[RefundStatus] = None
    provider_refund_id: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    processed_at: Optional[datetime] = None


class Refund(BaseModel):
    id: str
    payment_id: str
    order_id: str
    organization_id: str
    initiated_by_user_id: Optional[str] = None
    provider_code: str
    provider_refund_id: Optional[str] = None
    status: RefundStatus
    reason: RefundReason
    reason_details: Optional[str] = None
    currency: str
    amount: int
    idempotency_key: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================
# Webhook Event Schemas
# ============================================

class WebhookEventCreate(BaseModel):
    provider_code: str
    provider_event_id: str
    provider_event_type: str
    payload: Dict[str, Any]
    signature_verified: bool = False
    ip_address: Optional[str] = None


class WebhookEventUpdate(BaseModel):
    status: Optional[WebhookEventStatus] = None
    processed_at: Optional[datetime] = None
    processing_error: Optional[str] = None
    retry_count: Optional[int] = None
    next_retry_at: Optional[datetime] = None
    related_payment_id: Optional[str] = None
    related_order_id: Optional[str] = None
    related_refund_id: Optional[str] = None


class WebhookEvent(BaseModel):
    id: str
    provider_code: str
    provider_event_id: str
    provider_event_type: str
    status: WebhookEventStatus
    payload: Dict[str, Any]
    signature_verified: bool
    processed_at: Optional[datetime] = None
    processing_error: Optional[str] = None
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None
    related_payment_id: Optional[str] = None
    related_order_id: Optional[str] = None
    related_refund_id: Optional[str] = None
    received_at: datetime
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================
# Audit Log Schemas
# ============================================

class AuditLogCreate(BaseModel):
    action: str
    actor_type: str  # 'user', 'system', 'webhook', 'admin'
    actor_id: Optional[str] = None
    actor_ip: Optional[str] = None
    actor_user_agent: Optional[str] = None
    entity_type: str  # 'order', 'payment', 'refund'
    entity_id: str
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    change_details: Optional[Dict[str, Any]] = None
    organization_id: Optional[str] = None
    event_id: Optional[str] = None
    request_id: Optional[str] = None


class AuditLog(AuditLogCreate):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================
# Checkout Session Schemas
# ============================================

class PaymentIntentResponse(BaseModel):
    intent_id: str
    client_secret: str
    publishable_key: str
    expires_at: Optional[datetime] = None


class CheckoutSession(BaseModel):
    order: Order
    payment_intent: Optional[PaymentIntentResponse] = None
