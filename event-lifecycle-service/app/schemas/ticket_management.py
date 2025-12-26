# app/schemas/ticket_management.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ============================================
# Enums
# ============================================

class DiscountType(str, Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class TicketStatus(str, Enum):
    VALID = "valid"
    CHECKED_IN = "checked_in"
    CANCELLED = "cancelled"
    TRANSFERRED = "transferred"
    REFUNDED = "refunded"


# ============================================
# Money Schema
# ============================================

class Money(BaseModel):
    """Represents a monetary amount."""
    amount: int = Field(..., description="Amount in smallest currency unit (cents)")
    currency: str = Field(default="USD", description="ISO 4217 currency code")

    @property
    def formatted(self) -> str:
        """Format as human-readable string."""
        dollars = self.amount / 100
        if self.currency == "USD":
            return f"${dollars:,.2f}"
        return f"{self.currency} {dollars:,.2f}"


# ============================================
# Cart Item Schema (for validation)
# ============================================

class CartItem(BaseModel):
    """Represents an item in the cart for promo code validation."""
    ticket_type_id: str
    quantity: int = Field(..., ge=1)
    price: int = Field(..., ge=0, description="Price per ticket in cents")


# ============================================
# Ticket Type Schemas
# ============================================

class TicketTypeCreate(BaseModel):
    """Schema for creating a new ticket type."""
    event_id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price: int = Field(default=0, ge=0, description="Price in cents (0 for free)")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    quantity_total: Optional[int] = Field(default=None, ge=1, description="None = unlimited")
    min_per_order: int = Field(default=1, ge=1)
    max_per_order: int = Field(default=10, ge=1)
    sales_start_at: Optional[datetime] = None
    sales_end_at: Optional[datetime] = None
    is_hidden: bool = False
    sort_order: int = 0

    @field_validator('max_per_order')
    @classmethod
    def max_must_be_gte_min(cls, v, info):
        if 'min_per_order' in info.data and v < info.data['min_per_order']:
            raise ValueError('max_per_order must be >= min_per_order')
        return v

    @field_validator('sales_end_at')
    @classmethod
    def end_must_be_after_start(cls, v, info):
        if v and 'sales_start_at' in info.data and info.data['sales_start_at']:
            if v <= info.data['sales_start_at']:
                raise ValueError('sales_end_at must be after sales_start_at')
        return v


class TicketTypeUpdate(BaseModel):
    """Schema for updating a ticket type."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[int] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    quantity_total: Optional[int] = Field(default=None, ge=1)
    min_per_order: Optional[int] = Field(default=None, ge=1)
    max_per_order: Optional[int] = Field(default=None, ge=1)
    sales_start_at: Optional[datetime] = None
    sales_end_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    is_hidden: Optional[bool] = None
    sort_order: Optional[int] = None


class TicketTypeResponse(BaseModel):
    """Schema for ticket type response."""
    id: str
    event_id: str
    organization_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    price: int
    currency: str
    quantity_total: Optional[int] = None
    quantity_available: Optional[int] = None
    quantity_sold: int
    quantity_reserved: int
    min_per_order: int
    max_per_order: int
    sales_start_at: Optional[datetime] = None
    sales_end_at: Optional[datetime] = None
    is_active: bool
    is_hidden: bool
    is_on_sale: bool
    sort_order: int
    revenue: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TicketTypeStats(BaseModel):
    """Statistics for a ticket type."""
    ticket_type_id: str
    ticket_type_name: str
    quantity_sold: int
    quantity_available: Optional[int] = None
    revenue: Money
    percentage_sold: Optional[float] = None


class ReorderTicketTypesInput(BaseModel):
    """Input for reordering ticket types."""
    event_id: str
    ticket_type_ids: List[str]


# ============================================
# Promo Code Schemas
# ============================================

class PromoCodeCreate(BaseModel):
    """Schema for creating a promo code."""
    event_id: Optional[str] = None  # None = organization-wide
    code: str = Field(..., min_length=3, max_length=50)
    description: Optional[str] = None
    discount_type: DiscountType
    discount_value: int = Field(..., gt=0)
    applicable_ticket_type_ids: Optional[List[str]] = None
    max_uses: Optional[int] = Field(default=None, ge=1)
    max_uses_per_user: int = Field(default=1, ge=1)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    minimum_order_amount: Optional[int] = Field(default=None, ge=0, description="In cents")
    minimum_tickets: Optional[int] = Field(default=None, ge=1)

    @field_validator('discount_value')
    @classmethod
    def validate_discount_value(cls, v, info):
        if 'discount_type' in info.data:
            if info.data['discount_type'] == DiscountType.PERCENTAGE and v > 100:
                raise ValueError('Percentage discount cannot exceed 100')
        return v

    @field_validator('code')
    @classmethod
    def validate_code_format(cls, v):
        # Allow alphanumeric and dashes only
        import re
        if not re.match(r'^[A-Za-z0-9\-]+$', v):
            raise ValueError('Code must contain only letters, numbers, and dashes')
        return v.upper()  # Normalize to uppercase


class PromoCodeUpdate(BaseModel):
    """Schema for updating a promo code."""
    description: Optional[str] = None
    discount_type: Optional[DiscountType] = None
    discount_value: Optional[int] = Field(default=None, gt=0)
    applicable_ticket_type_ids: Optional[List[str]] = None
    max_uses: Optional[int] = Field(default=None, ge=1)
    max_uses_per_user: Optional[int] = Field(default=None, ge=1)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    minimum_order_amount: Optional[int] = Field(default=None, ge=0)
    minimum_tickets: Optional[int] = Field(default=None, ge=1)
    is_active: Optional[bool] = None


class PromoCodeResponse(BaseModel):
    """Schema for promo code response."""
    id: str
    event_id: Optional[str] = None
    organization_id: str
    code: str
    description: Optional[str] = None
    discount_type: DiscountType
    discount_value: int
    discount_formatted: str
    applicable_ticket_type_ids: Optional[List[str]] = None
    max_uses: Optional[int] = None
    max_uses_per_user: int
    current_uses: int
    remaining_uses: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_currently_valid: bool
    minimum_order_amount: Optional[int] = None
    minimum_tickets: Optional[int] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PromoCodeValidation(BaseModel):
    """Result of promo code validation."""
    is_valid: bool
    promo_code: Optional[PromoCodeResponse] = None
    discount_amount: Optional[Money] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


# ============================================
# Ticket Schemas
# ============================================

class TicketResponse(BaseModel):
    """Schema for ticket response."""
    id: str
    ticket_code: str
    event_id: str
    order_id: str
    ticket_type_id: str
    attendee_name: str
    attendee_email: str
    status: TicketStatus
    checked_in_at: Optional[datetime] = None
    checked_in_by: Optional[str] = None
    check_in_location: Optional[str] = None
    qr_code_url: str
    created_at: datetime

    class Config:
        from_attributes = True


class CheckInTicketInput(BaseModel):
    """Input for checking in a ticket."""
    ticket_code: str
    event_id: str
    location: Optional[str] = None


class TransferTicketInput(BaseModel):
    """Input for transferring a ticket."""
    ticket_id: str
    new_attendee_name: str = Field(..., min_length=1, max_length=255)
    new_attendee_email: str = Field(..., max_length=255)

    @field_validator('new_attendee_email')
    @classmethod
    def validate_email(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', v):
            raise ValueError('Invalid email format')
        return v.lower()


class CancelTicketInput(BaseModel):
    """Input for cancelling a ticket."""
    ticket_id: str
    reason: Optional[str] = None


# ============================================
# Event Ticket Summary Schemas
# ============================================

class EventTicketSummary(BaseModel):
    """Summary of ticket sales for an event."""
    event_id: str
    total_ticket_types: int
    total_capacity: Optional[int] = None  # None if any ticket type is unlimited
    total_sold: int
    total_revenue: Money
    ticket_type_stats: List[TicketTypeStats]
    # Sales by time period
    sales_today: int
    sales_this_week: int
    sales_this_month: int
    # Revenue by time period
    revenue_today: Money
    revenue_this_week: Money
    revenue_this_month: Money


# ============================================
# Promo Code Usage Schema
# ============================================

class PromoCodeUsageResponse(BaseModel):
    """Schema for promo code usage tracking."""
    id: str
    promo_code_id: str
    order_id: str
    user_id: Optional[str] = None
    guest_email: Optional[str] = None
    discount_applied: int
    used_at: datetime

    class Config:
        from_attributes = True
