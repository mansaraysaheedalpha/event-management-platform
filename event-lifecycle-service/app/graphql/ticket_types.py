# app/graphql/ticket_types.py
"""
GraphQL types for Ticket Management System
"""
import strawberry
from typing import Optional, List
from datetime import datetime
from enum import Enum

from app.models.ticket_type import TicketType as TicketTypeModel
from app.models.promo_code import PromoCode as PromoCodeModel
from app.models.ticket import Ticket as TicketModel
from app.graphql.payment_types import MoneyType, TicketTypeType as BaseTicketTypeType


# ============================================
# Enums
# ============================================

@strawberry.enum
class DiscountTypeEnum(Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


@strawberry.enum
class TicketStatusEnum(Enum):
    VALID = "valid"
    CHECKED_IN = "checked_in"
    CANCELLED = "cancelled"
    TRANSFERRED = "transferred"
    REFUNDED = "refunded"


# ============================================
# Extended Ticket Type (for organizers)
# ============================================

@strawberry.type
class TicketTypeFullType:
    """Extended ticket type with all fields for organizers."""
    id: str
    name: str
    description: Optional[str]

    @strawberry.field
    def sortOrder(self, root: TicketTypeModel) -> int:
        return root.sort_order

    @strawberry.field
    def eventId(self, root: TicketTypeModel) -> str:
        return root.event_id

    @strawberry.field
    def organizationId(self, root: TicketTypeModel) -> Optional[str]:
        return root.organization_id

    @strawberry.field
    def price(self, root: TicketTypeModel) -> MoneyType:
        return MoneyType(amount=root.price, currency=root.currency)

    @strawberry.field
    def quantityTotal(self, root: TicketTypeModel) -> Optional[int]:
        return root.quantity_total

    @strawberry.field
    def quantityAvailable(self, root: TicketTypeModel) -> Optional[int]:
        return root.quantity_available

    @strawberry.field
    def quantitySold(self, root: TicketTypeModel) -> int:
        return root.quantity_sold

    @strawberry.field
    def quantityReserved(self, root: TicketTypeModel) -> int:
        return root.quantity_reserved

    @strawberry.field
    def minPerOrder(self, root: TicketTypeModel) -> int:
        return root.min_per_order

    @strawberry.field
    def maxPerOrder(self, root: TicketTypeModel) -> int:
        return root.max_per_order

    @strawberry.field
    def salesStartAt(self, root: TicketTypeModel) -> Optional[datetime]:
        return root.sales_start_at

    @strawberry.field
    def salesEndAt(self, root: TicketTypeModel) -> Optional[datetime]:
        return root.sales_end_at

    @strawberry.field
    def isActive(self, root: TicketTypeModel) -> bool:
        return root.is_active

    @strawberry.field
    def isHidden(self, root: TicketTypeModel) -> bool:
        return root.is_hidden

    @strawberry.field
    def isOnSale(self, root: TicketTypeModel) -> bool:
        return root.is_on_sale

    @strawberry.field
    def revenue(self, root: TicketTypeModel) -> MoneyType:
        return MoneyType(amount=root.revenue, currency=root.currency)

    @strawberry.field
    def createdAt(self, root: TicketTypeModel) -> datetime:
        return root.created_at

    @strawberry.field
    def updatedAt(self, root: TicketTypeModel) -> datetime:
        return root.updated_at


# ============================================
# Ticket Type Stats
# ============================================

@strawberry.type
class TicketTypeStatsType:
    """Statistics for a ticket type."""
    ticketTypeId: str
    ticketTypeName: str
    quantitySold: int
    quantityAvailable: Optional[int]
    revenue: MoneyType
    percentageSold: Optional[float]


# ============================================
# Promo Code Types
# ============================================

@strawberry.type
class PromoCodeFullType:
    """Full promo code type for organizers."""
    id: str
    code: str
    description: Optional[str]

    @strawberry.field
    def eventId(self, root: PromoCodeModel) -> Optional[str]:
        return root.event_id

    @strawberry.field
    def organizationId(self, root: PromoCodeModel) -> str:
        return root.organization_id

    @strawberry.field
    def discountType(self, root: PromoCodeModel) -> DiscountTypeEnum:
        return DiscountTypeEnum(root.discount_type)

    @strawberry.field
    def discountValue(self, root: PromoCodeModel) -> int:
        return root.discount_value

    @strawberry.field
    def discountFormatted(self, root: PromoCodeModel) -> str:
        return root.discount_formatted

    @strawberry.field
    def applicableTicketTypeIds(self, root: PromoCodeModel) -> Optional[List[str]]:
        return root.applicable_ticket_type_ids

    @strawberry.field
    def applicableTicketTypes(self, root: PromoCodeModel, info) -> List[TicketTypeFullType]:
        """Get the actual ticket type objects this promo code applies to."""
        if not root.applicable_ticket_type_ids:
            return []
        db = info.context.db
        from app.crud.ticket_type_v2 import ticket_type_crud
        ticket_types = []
        for tt_id in root.applicable_ticket_type_ids:
            tt = ticket_type_crud.get(db, tt_id)
            if tt:
                ticket_types.append(tt)
        return ticket_types

    @strawberry.field
    def maxUses(self, root: PromoCodeModel) -> Optional[int]:
        return root.max_uses

    @strawberry.field
    def maxUsesPerUser(self, root: PromoCodeModel) -> int:
        return root.max_uses_per_user

    @strawberry.field
    def currentUses(self, root: PromoCodeModel) -> int:
        return root.current_uses

    @strawberry.field
    def remainingUses(self, root: PromoCodeModel) -> Optional[int]:
        return root.remaining_uses

    @strawberry.field
    def validFrom(self, root: PromoCodeModel) -> Optional[datetime]:
        return root.valid_from

    @strawberry.field
    def validUntil(self, root: PromoCodeModel) -> Optional[datetime]:
        return root.valid_until

    @strawberry.field
    def isCurrentlyValid(self, root: PromoCodeModel) -> bool:
        return root.is_currently_valid

    @strawberry.field
    def minimumOrderAmount(self, root: PromoCodeModel) -> Optional[MoneyType]:
        if root.minimum_order_amount:
            return MoneyType(amount=root.minimum_order_amount, currency=root.currency or "USD")
        return None

    @strawberry.field
    def minimumTickets(self, root: PromoCodeModel) -> Optional[int]:
        return root.minimum_tickets

    @strawberry.field
    def isActive(self, root: PromoCodeModel) -> bool:
        return root.is_active

    @strawberry.field
    def createdAt(self, root: PromoCodeModel) -> datetime:
        return root.created_at


@strawberry.type
class PromoCodeValidationType:
    """Result of promo code validation."""
    isValid: bool
    promoCode: Optional[PromoCodeFullType] = None
    discountAmount: Optional[MoneyType] = None
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None


# ============================================
# Ticket Types (Issued Tickets)
# ============================================

@strawberry.type
class TicketType:
    """Issued ticket for an attendee."""
    id: str

    @strawberry.field
    def ticketCode(self, root: TicketModel) -> str:
        return root.ticket_code

    @strawberry.field
    def eventId(self, root: TicketModel) -> str:
        return root.event_id

    @strawberry.field
    def orderId(self, root: TicketModel) -> str:
        return root.order_id

    @strawberry.field
    def ticketTypeId(self, root: TicketModel) -> str:
        return root.ticket_type_id

    @strawberry.field
    def ticketTypeName(self, root: TicketModel) -> str:
        if root.ticket_type:
            return root.ticket_type.name
        return ""

    @strawberry.field
    def attendeeName(self, root: TicketModel) -> str:
        return root.attendee_name

    @strawberry.field
    def attendeeEmail(self, root: TicketModel) -> str:
        return root.attendee_email

    @strawberry.field
    def status(self, root: TicketModel) -> TicketStatusEnum:
        return TicketStatusEnum(root.status)

    @strawberry.field
    def checkedInAt(self, root: TicketModel) -> Optional[datetime]:
        return root.checked_in_at

    @strawberry.field
    def checkedInBy(self, root: TicketModel) -> Optional[str]:
        return root.checked_in_by

    @strawberry.field
    def checkInLocation(self, root: TicketModel) -> Optional[str]:
        return root.check_in_location

    @strawberry.field
    def qrCodeData(self, root: TicketModel) -> Optional[str]:
        """Signed JWT token for embedding in QR code.

        This is the cryptographically signed payload that should be
        encoded into the QR code image. Scanner apps verify the JWT
        signature to prevent forgery.
        """
        return root.qr_code_data

    @strawberry.field
    def qrCodeUrl(self, root: TicketModel) -> str:
        return root.qr_code_url

    @strawberry.field
    def expiresAt(self, root: TicketModel) -> Optional[datetime]:
        """Ticket expiration timestamp, if set."""
        return root.expires_at

    @strawberry.field
    def createdAt(self, root: TicketModel) -> datetime:
        return root.created_at


@strawberry.type
class TicketConnection:
    """Paginated ticket list."""
    tickets: List[TicketType]
    totalCount: int
    hasNextPage: bool


# ============================================
# Event Ticket Summary
# ============================================

@strawberry.type
class EventTicketSummaryType:
    """Comprehensive ticket summary for an event."""
    eventId: str
    totalTicketTypes: int
    totalCapacity: Optional[int]  # None if any type is unlimited
    totalSold: int
    totalRevenue: MoneyType
    ticketTypeStats: List[TicketTypeStatsType]
    salesToday: int
    salesThisWeek: int
    salesThisMonth: int
    revenueToday: MoneyType
    revenueThisWeek: MoneyType
    revenueThisMonth: MoneyType


# ============================================
# Check-in Stats
# ============================================

@strawberry.type
class CheckInStatsType:
    """Check-in statistics for an event."""
    total: int
    checkedIn: int
    remaining: int
    percentage: float


# ============================================
# Input Types
# ============================================

@strawberry.input
class CreateTicketTypeInput:
    """Input for creating a ticket type."""
    eventId: str
    name: str
    description: Optional[str] = None
    price: int = 0  # In cents (0 for free)
    currency: str = "USD"
    quantityTotal: Optional[int] = None  # None = unlimited
    minPerOrder: int = 1
    maxPerOrder: int = 10
    salesStartAt: Optional[datetime] = None
    salesEndAt: Optional[datetime] = None
    isActive: bool = True
    isHidden: bool = False
    sortOrder: int = 0


@strawberry.input
class UpdateTicketTypeInput:
    """Input for updating a ticket type."""
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    currency: Optional[str] = None
    quantityTotal: Optional[int] = None
    minPerOrder: Optional[int] = None
    maxPerOrder: Optional[int] = None
    salesStartAt: Optional[datetime] = None
    salesEndAt: Optional[datetime] = None
    isActive: Optional[bool] = None
    isHidden: Optional[bool] = None
    sortOrder: Optional[int] = None


@strawberry.input
class ReorderTicketTypesInput:
    """Input for reordering ticket types."""
    eventId: str
    ticketTypeIds: List[str]


@strawberry.input
class CreatePromoCodeInput:
    """Input for creating a promo code."""
    eventId: Optional[str] = None  # None = organization-wide
    code: str
    description: Optional[str] = None
    discountType: DiscountTypeEnum
    discountValue: int
    applicableTicketTypeIds: Optional[List[str]] = None
    maxUses: Optional[int] = None
    maxUsesPerUser: int = 1
    validFrom: Optional[datetime] = None
    validUntil: Optional[datetime] = None
    minimumOrderAmount: Optional[int] = None  # In cents
    minimumTickets: Optional[int] = None


@strawberry.input
class UpdatePromoCodeInput:
    """Input for updating a promo code."""
    description: Optional[str] = None
    discountType: Optional[DiscountTypeEnum] = None
    discountValue: Optional[int] = None
    applicableTicketTypeIds: Optional[List[str]] = None
    maxUses: Optional[int] = None
    maxUsesPerUser: Optional[int] = None
    validFrom: Optional[datetime] = None
    validUntil: Optional[datetime] = None
    minimumOrderAmount: Optional[int] = None
    minimumTickets: Optional[int] = None
    isActive: Optional[bool] = None


@strawberry.input
class CartItemInput:
    """Cart item for promo code validation."""
    ticketTypeId: str
    quantity: int
    price: int  # Price per ticket in cents


@strawberry.input
class CheckInTicketInput:
    """Input for checking in a ticket."""
    ticketCode: str
    eventId: str
    location: Optional[str] = None
    idempotencyKey: Optional[str] = None


@strawberry.input
class TransferTicketInput:
    """Input for transferring a ticket."""
    ticketId: str
    newAttendeeName: str
    newAttendeeEmail: str


@strawberry.input
class TransferMyTicketInput:
    """Input for an attendee transferring their own ticket by ticket code."""
    ticketCode: str
    newAttendeeName: str
    newAttendeeEmail: str


@strawberry.input
class CancelTicketInput:
    """Input for cancelling a ticket."""
    ticketId: str
    reason: Optional[str] = None
