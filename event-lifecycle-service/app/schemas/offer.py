# app/schemas/offer.py
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


# ==================== Enums ====================

class OfferType(str):
    TICKET_UPGRADE = "TICKET_UPGRADE"
    MERCHANDISE = "MERCHANDISE"
    EXCLUSIVE_CONTENT = "EXCLUSIVE_CONTENT"
    SERVICE = "SERVICE"


class PlacementType(str):
    CHECKOUT = "CHECKOUT"
    POST_PURCHASE = "POST_PURCHASE"
    IN_EVENT = "IN_EVENT"
    EMAIL = "EMAIL"


class FulfillmentStatus(str):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    FULFILLED = "FULFILLED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class FulfillmentType(str):
    DIGITAL = "DIGITAL"
    PHYSICAL = "PHYSICAL"
    SERVICE = "SERVICE"
    TICKET = "TICKET"


# ==================== Inventory Status ====================

class InventoryStatus(BaseModel):
    """Inventory status for an offer."""
    total: Optional[int] = Field(None, description="Total inventory (null = unlimited)")
    available: int = Field(..., description="Available inventory")
    sold: int = Field(0, description="Sold quantity")
    reserved: int = Field(0, description="Reserved quantity")


# ==================== Offer Schemas ====================

class OfferBase(BaseModel):
    """Base offer fields."""
    event_id: str = Field(..., min_length=1, description="Event ID", examples=["evt_abc123"])
    title: str = Field(..., min_length=1, max_length=255, description="Offer title", examples=["VIP Upgrade"])
    description: Optional[str] = Field(None, description="Offer description")
    offer_type: str = Field(..., description="Offer type", examples=["TICKET_UPGRADE", "MERCHANDISE", "EXCLUSIVE_CONTENT", "SERVICE"])
    price: float = Field(..., ge=0, description="Price in currency units", examples=[99.99])
    original_price: Optional[float] = Field(None, ge=0, description="Original price (for discount display)")
    currency: str = Field("USD", min_length=3, max_length=3, pattern="^[A-Z]{3}$", description="Currency code")
    image_url: Optional[str] = Field(None, description="Offer image URL")

    @field_validator('offer_type')
    @classmethod
    def validate_offer_type(cls, v):
        valid_types = ["TICKET_UPGRADE", "MERCHANDISE", "EXCLUSIVE_CONTENT", "SERVICE"]
        if v not in valid_types:
            raise ValueError(f"offer_type must be one of {valid_types}")
        return v

    @model_validator(mode='after')
    def validate_original_price(self):
        if self.original_price is not None and self.original_price < self.price:
            raise ValueError("original_price must be greater than or equal to price")
        return self


class OfferCreate(OfferBase):
    """Schema for creating a new offer."""
    inventory_total: Optional[int] = Field(None, gt=0, description="Total inventory (null = unlimited)")
    placement: str = Field("IN_EVENT", description="Placement type", examples=["CHECKOUT", "POST_PURCHASE", "IN_EVENT", "EMAIL"])
    target_sessions: List[str] = Field(default_factory=list, description="Target session IDs (empty = all sessions)")
    target_ticket_tiers: List[str] = Field(default_factory=list, description="Target ticket tiers (empty = all tiers)")
    starts_at: Optional[datetime] = Field(None, description="Offer start time")
    expires_at: Optional[datetime] = Field(None, description="Offer expiration time")

    @field_validator('placement')
    @classmethod
    def validate_placement(cls, v):
        valid_placements = ["CHECKOUT", "POST_PURCHASE", "IN_EVENT", "EMAIL"]
        if v not in valid_placements:
            raise ValueError(f"placement must be one of {valid_placements}")
        return v

    @model_validator(mode='after')
    def validate_time_window(self):
        if self.starts_at and self.expires_at and self.starts_at >= self.expires_at:
            raise ValueError("starts_at must be before expires_at")
        return self


class OfferUpdate(BaseModel):
    """Schema for updating an existing offer."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    original_price: Optional[float] = Field(None, ge=0)
    image_url: Optional[str] = None
    inventory_total: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None
    placement: Optional[str] = None
    target_sessions: Optional[List[str]] = None
    target_ticket_tiers: Optional[List[str]] = None

    @field_validator('placement')
    @classmethod
    def validate_placement(cls, v):
        if v is not None:
            valid_placements = ["CHECKOUT", "POST_PURCHASE", "IN_EVENT", "EMAIL"]
            if v not in valid_placements:
                raise ValueError(f"placement must be one of {valid_placements}")
        return v


class OfferResponse(BaseModel):
    """Full offer response with all fields."""
    id: str
    event_id: str
    organization_id: str
    title: str
    description: Optional[str]
    offer_type: str
    price: float
    original_price: Optional[float]
    currency: str
    image_url: Optional[str]

    # Inventory
    inventory: InventoryStatus

    # Targeting & Placement
    placement: str
    target_sessions: List[str]
    target_ticket_tiers: List[str]

    # Stripe
    stripe_product_id: Optional[str]
    stripe_price_id: Optional[str]

    # Scheduling
    starts_at: Optional[datetime]
    expires_at: Optional[datetime]

    # Status
    is_active: bool
    is_archived: bool
    is_available: bool = Field(..., description="Computed: is offer currently available to purchase")

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class Offer(OfferBase):
    """Legacy offer schema for backward compatibility."""
    id: str
    organization_id: str
    is_archived: bool

    model_config = {"from_attributes": True}


# ==================== Offer Purchase Schemas ====================

class OfferPurchaseCreate(BaseModel):
    """Schema for purchasing an offer."""
    offer_id: str = Field(..., description="Offer ID to purchase")
    quantity: int = Field(1, gt=0, le=20, description="Quantity to purchase (max 20)")


class OfferPurchaseResponse(BaseModel):
    """Offer purchase response."""
    id: str
    offer_id: str
    user_id: str
    order_id: Optional[str]

    # Purchase Details
    quantity: int
    unit_price: float
    total_price: float
    currency: str

    # Fulfillment
    fulfillment_status: str
    fulfillment_type: Optional[str]
    digital_content_url: Optional[str]
    access_code: Optional[str]
    tracking_number: Optional[str]

    # Timestamps
    purchased_at: datetime
    fulfilled_at: Optional[datetime]
    refunded_at: Optional[datetime]

    model_config = {"from_attributes": True}


class OfferWithPurchases(OfferResponse):
    """Offer with user's purchase history."""
    purchases: List[OfferPurchaseResponse] = []

    model_config = {"from_attributes": True}


# ==================== Helper Schemas ====================

class OfferAvailabilityCheck(BaseModel):
    """Check if offer is available for purchase."""
    offer_id: str
    quantity: int = 1


class OfferAvailabilityResponse(BaseModel):
    """Availability check response."""
    available: bool
    reason: Optional[str] = None
    inventory_available: int
