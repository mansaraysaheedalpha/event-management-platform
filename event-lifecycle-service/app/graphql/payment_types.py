# app/graphql/payment_types.py
import strawberry
from strawberry.types import Info
from typing import Optional, List
from datetime import datetime
from enum import Enum

from app.models.ticket_type import TicketType as TicketTypeModel
from app.models.promo_code import PromoCode as PromoCodeModel
from app.models.order import Order as OrderModel
from app.models.order_item import OrderItem as OrderItemModel
from app.graphql.connect_types import FeeAbsorption
from app.models.payment import Payment as PaymentModel
from app.models.refund import Refund as RefundModel


# ============================================
# Enums
# ============================================

@strawberry.enum
class OrderStatusEnum(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    EXPIRED = "expired"


@strawberry.enum
class PaymentStatusEnum(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


@strawberry.enum
class RefundStatusEnum(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@strawberry.enum
class RefundReasonEnum(Enum):
    REQUESTED_BY_CUSTOMER = "requested_by_customer"
    DUPLICATE = "duplicate"
    FRAUDULENT = "fraudulent"
    EVENT_CANCELLED = "event_cancelled"
    OTHER = "other"


# FeeAbsorption enum is imported from connect_types (single source of truth)


# ============================================
# Money Type
# ============================================

@strawberry.type
class MoneyType:
    """Represents a monetary amount with currency."""
    amount: int  # In smallest currency unit (cents)
    currency: str

    @strawberry.field
    def formatted(self) -> str:
        """Format amount as currency string."""
        symbols = {"USD": "$", "EUR": "€", "GBP": "£", "CAD": "C$", "AUD": "A$"}
        symbol = symbols.get(self.currency.upper(), self.currency + " ")
        return f"{symbol}{self.amount / 100:.2f}"


# ============================================
# Ticket Type
# ============================================

@strawberry.type
class TicketTypeType:
    """Ticket type/tier for an event."""
    id: str
    name: str
    description: Optional[str]

    @strawberry.field
    def sortOrder(self, root: TicketTypeModel) -> int:
        return root.sort_order

    @strawberry.field
    def price(self, root: TicketTypeModel) -> MoneyType:
        return MoneyType(amount=root.price, currency=root.currency)

    @strawberry.field
    def quantityTotal(self, root: TicketTypeModel) -> Optional[int]:
        return root.quantity_total

    @strawberry.field
    def quantityAvailable(self, root: TicketTypeModel) -> Optional[int]:
        if root.quantity_total is None:
            return None
        return max(0, root.quantity_total - root.quantity_sold)

    @strawberry.field
    def quantitySold(self, root: TicketTypeModel) -> int:
        return root.quantity_sold

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
        """Check if ticket type is currently on sale."""
        from datetime import timezone
        if not root.is_active:
            return False

        now = datetime.now(timezone.utc)

        if root.sales_start_at and now < root.sales_start_at:
            return False
        if root.sales_end_at and now > root.sales_end_at:
            return False

        return True

    @strawberry.field
    def isSoldOut(self, root: TicketTypeModel) -> bool:
        """Check if ticket type is sold out."""
        if root.quantity_total is None:
            return False
        return root.quantity_sold >= root.quantity_total


# ============================================
# Promo Code
# ============================================

@strawberry.type
class PromoCodeType:
    """Promotional code for discounts."""
    id: str
    code: str

    @strawberry.field
    def description(self, root: PromoCodeModel) -> Optional[str]:
        return root.description

    @strawberry.field
    def discountType(self, root: PromoCodeModel) -> str:
        return root.discount_type

    @strawberry.field
    def discountValue(self, root: PromoCodeModel) -> int:
        return root.discount_value

    @strawberry.field
    def discountFormatted(self, root: PromoCodeModel) -> str:
        return root.discount_formatted

    @strawberry.field
    def currency(self, root: PromoCodeModel) -> Optional[str]:
        return root.currency

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
    def timesUsed(self, root: PromoCodeModel) -> int:
        return root.times_used

    @strawberry.field
    def applicableTicketTypeIds(self, root: PromoCodeModel) -> Optional[List[str]]:
        return root.applicable_ticket_type_ids

    @strawberry.field
    def applicableTicketTypes(self, root: PromoCodeModel, info: Info) -> List["TicketTypeType"]:
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
    def minimumOrderAmount(self, root: PromoCodeModel) -> Optional[int]:
        return root.minimum_order_amount

    @strawberry.field
    def minimumTickets(self, root: PromoCodeModel) -> Optional[int]:
        return root.minimum_tickets

    @strawberry.field
    def validFrom(self, root: PromoCodeModel) -> Optional[datetime]:
        return root.valid_from

    @strawberry.field
    def validUntil(self, root: PromoCodeModel) -> Optional[datetime]:
        return root.valid_until

    @strawberry.field
    def isActive(self, root: PromoCodeModel) -> bool:
        return root.is_active

    @strawberry.field
    def isCurrentlyValid(self, root: PromoCodeModel) -> bool:
        return root.is_currently_valid

    @strawberry.field
    def isValid(self, root: PromoCodeModel) -> bool:
        return root.is_valid

    @strawberry.field
    def createdAt(self, root: PromoCodeModel) -> datetime:
        return root.created_at


# ============================================
# Order Item
# ============================================

@strawberry.type
class OrderItemType:
    """Line item in an order."""
    id: str
    quantity: int

    @strawberry.field
    def ticketTypeId(self, root: OrderItemModel) -> str:
        return root.ticket_type_id

    @strawberry.field
    def ticketTypeName(self, root: OrderItemModel) -> str:
        return root.ticket_type_name

    @strawberry.field
    def ticketTypeDescription(self, root: OrderItemModel) -> Optional[str]:
        return root.ticket_type_description

    @strawberry.field
    def unitPrice(self, root: OrderItemModel) -> MoneyType:
        # Get currency from order
        currency = root.order.currency if root.order else "USD"
        return MoneyType(amount=root.unit_price, currency=currency)

    @strawberry.field
    def totalPrice(self, root: OrderItemModel) -> MoneyType:
        currency = root.order.currency if root.order else "USD"
        return MoneyType(amount=root.total_price, currency=currency)


# ============================================
# Fee Breakdown Types
# ============================================

@strawberry.type
class ItemFeeType:
    """Per-item fee breakdown for a ticket type in an order."""
    ticketTypeName: str
    quantity: int
    unitPrice: int        # cents
    feePerTicket: int     # cents
    feeSubtotal: int      # cents (feePerTicket * quantity)


@strawberry.type
class FeeBreakdownType:
    """Fee breakdown for an order, showing how platform fees were calculated."""
    platformFeePercent: float
    platformFeeFixed: int       # cents
    platformFeeTotal: int       # cents
    perItemFees: List[ItemFeeType]


# ============================================
# Order
# ============================================

@strawberry.type
class OrderType:
    """Order/purchase record."""
    id: str

    @strawberry.field
    def orderNumber(self, root: OrderModel) -> str:
        return root.order_number

    @strawberry.field
    def eventId(self, root: OrderModel) -> str:
        return root.event_id

    @strawberry.field
    def status(self, root: OrderModel) -> OrderStatusEnum:
        return OrderStatusEnum(root.status)

    @strawberry.field
    def customerEmail(self, root: OrderModel) -> str:
        return root.guest_email or ""

    @strawberry.field
    def customerName(self, root: OrderModel) -> str:
        if root.guest_first_name or root.guest_last_name:
            return f"{root.guest_first_name or ''} {root.guest_last_name or ''}".strip()
        return ""

    @strawberry.field
    def isGuestOrder(self, root: OrderModel) -> bool:
        return root.user_id is None

    @strawberry.field
    def items(self, root: OrderModel) -> List[OrderItemType]:
        return root.items or []

    @strawberry.field
    def subtotal(self, root: OrderModel) -> MoneyType:
        return MoneyType(amount=root.subtotal, currency=root.currency)

    @strawberry.field
    def discountAmount(self, root: OrderModel) -> MoneyType:
        return MoneyType(amount=root.discount_amount, currency=root.currency)

    @strawberry.field
    def taxAmount(self, root: OrderModel) -> MoneyType:
        return MoneyType(amount=root.tax_amount, currency=root.currency)

    @strawberry.field
    def totalAmount(self, root: OrderModel) -> MoneyType:
        return MoneyType(amount=root.total_amount, currency=root.currency)

    @strawberry.field
    def subtotalAmount(self, root: OrderModel) -> Optional[MoneyType]:
        """Original ticket prices before fee adjustments (pass_to_buyer model)."""
        if root.subtotal_amount is not None:
            return MoneyType(amount=root.subtotal_amount, currency=root.currency)
        return None

    @strawberry.field
    def platformFee(self, root: OrderModel) -> MoneyType:
        """Platform fee charged on this order."""
        return MoneyType(amount=root.platform_fee, currency=root.currency)

    @strawberry.field
    def feeAbsorption(self, root: OrderModel) -> Optional[FeeAbsorption]:
        """Who pays the platform fee: organizer (absorb) or buyer (pass_to_buyer)."""
        if root.fee_absorption:
            try:
                return FeeAbsorption(root.fee_absorption)
            except ValueError:
                return None
        return None

    @strawberry.field
    def feeBreakdown(self, root: OrderModel) -> Optional[FeeBreakdownType]:
        """Detailed fee breakdown showing how platform fees were calculated."""
        if not root.fee_breakdown_json:
            return None
        data = root.fee_breakdown_json
        per_item_fees = [
            ItemFeeType(
                ticketTypeName=item.get("ticket_type_name", ""),
                quantity=item.get("quantity", 0),
                unitPrice=item.get("unit_price", 0),
                feePerTicket=item.get("fee_per_ticket", 0),
                feeSubtotal=item.get("fee_subtotal", 0),
            )
            for item in data.get("per_item_fees", [])
        ]
        return FeeBreakdownType(
            platformFeePercent=data.get("fee_percent_used", 0.0),
            platformFeeFixed=data.get("fee_fixed_used", 0),
            platformFeeTotal=data.get("platform_fee_total", 0),
            perItemFees=per_item_fees,
        )

    @strawberry.field
    def promoCode(self, root: OrderModel) -> Optional["PromoCodeType"]:
        """
        Promo code applied to this order, if any.
        """
        return root.promo_code

    @strawberry.field
    def expiresAt(self, root: OrderModel) -> Optional[datetime]:
        return root.expires_at

    @strawberry.field
    def completedAt(self, root: OrderModel) -> Optional[datetime]:
        return root.completed_at

    @strawberry.field
    def createdAt(self, root: OrderModel) -> datetime:
        return root.created_at


# ============================================
# Payment
# ============================================

@strawberry.type
class PaymentType:
    """Payment transaction record."""
    id: str

    @strawberry.field
    def status(self, root: PaymentModel) -> PaymentStatusEnum:
        return PaymentStatusEnum(root.status)

    @strawberry.field
    def amount(self, root: PaymentModel) -> MoneyType:
        return MoneyType(amount=root.amount, currency=root.currency)

    @strawberry.field
    def amountRefunded(self, root: PaymentModel) -> MoneyType:
        return MoneyType(amount=root.amount_refunded, currency=root.currency)

    @strawberry.field
    def providerFee(self, root: PaymentModel) -> MoneyType:
        return MoneyType(amount=root.provider_fee, currency=root.currency)

    @strawberry.field
    def netAmount(self, root: PaymentModel) -> MoneyType:
        return MoneyType(amount=root.net_amount, currency=root.currency)

    @strawberry.field
    def paymentMethodType(self, root: PaymentModel) -> Optional[str]:
        return root.payment_method_type

    @strawberry.field
    def paymentMethodBrand(self, root: PaymentModel) -> Optional[str]:
        if root.payment_method_details:
            return root.payment_method_details.get("brand")
        return None

    @strawberry.field
    def paymentMethodLast4(self, root: PaymentModel) -> Optional[str]:
        if root.payment_method_details:
            return root.payment_method_details.get("last4")
        return None

    @strawberry.field
    def processedAt(self, root: PaymentModel) -> Optional[datetime]:
        return root.processed_at

    @strawberry.field
    def createdAt(self, root: PaymentModel) -> datetime:
        return root.created_at


# ============================================
# Refund
# ============================================

@strawberry.type
class RefundType:
    """Refund transaction record."""
    id: str

    @strawberry.field
    def status(self, root: RefundModel) -> RefundStatusEnum:
        return RefundStatusEnum(root.status)

    @strawberry.field
    def amount(self, root: RefundModel) -> MoneyType:
        return MoneyType(amount=root.amount, currency=root.currency)

    @strawberry.field
    def reason(self, root: RefundModel) -> RefundReasonEnum:
        return RefundReasonEnum(root.reason)

    @strawberry.field
    def reasonDetails(self, root: RefundModel) -> Optional[str]:
        return root.reason_details

    @strawberry.field
    def processedAt(self, root: RefundModel) -> Optional[datetime]:
        return root.processed_at

    @strawberry.field
    def createdAt(self, root: RefundModel) -> datetime:
        return root.created_at


# ============================================
# Payment Intent Response
# ============================================

@strawberry.type
class PaymentIntentType:
    """Payment intent for client-side checkout."""
    clientSecret: str
    intentId: str
    publishableKey: str
    expiresAt: Optional[datetime]


# ============================================
# Checkout Session Response
# ============================================

@strawberry.type
class CheckoutSessionType:
    """Checkout session with order and payment intent."""
    order: OrderType
    paymentIntent: Optional[PaymentIntentType]


# ============================================
# Pagination
# ============================================

@strawberry.type
class OrderConnection:
    """Paginated order list."""
    orders: List[OrderType]
    totalCount: int
    hasNextPage: bool


# ============================================
# Input Types
# ============================================

@strawberry.input
class OrderItemInput:
    """Input for creating an order item."""
    ticketTypeId: str
    quantity: int


@strawberry.input
class CreateOrderInput:
    """Input for creating an order/checkout session."""
    eventId: str
    items: List[OrderItemInput]
    promoCode: Optional[str] = None
    guestEmail: Optional[str] = None
    guestFirstName: Optional[str] = None
    guestLastName: Optional[str] = None
    guestPhone: Optional[str] = None


@strawberry.input
class InitiateRefundInput:
    """Input for initiating a refund."""
    orderId: str
    amount: Optional[int] = None  # Optional for full refund
    reason: RefundReasonEnum
    reasonDetails: Optional[str] = None


@strawberry.input
class TicketTypeCreateInput:
    """Input for creating a ticket type."""
    eventId: str
    name: str
    description: Optional[str] = None
    price: int = 0
    currency: str = "USD"
    quantityTotal: Optional[int] = None
    minPerOrder: int = 1
    maxPerOrder: int = 10
    salesStartAt: Optional[datetime] = None
    salesEndAt: Optional[datetime] = None
    isActive: bool = True
    isHidden: bool = False
    sortOrder: int = 0


@strawberry.input
class TicketTypeUpdateInput:
    """Input for updating a ticket type."""
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    quantityTotal: Optional[int] = None
    minPerOrder: Optional[int] = None
    maxPerOrder: Optional[int] = None
    salesStartAt: Optional[datetime] = None
    salesEndAt: Optional[datetime] = None
    isActive: Optional[bool] = None
    isHidden: Optional[bool] = None
    sortOrder: Optional[int] = None


@strawberry.input
class PromoCodeCreateInput:
    """Input for creating a promo code."""
    code: str
    discountType: str  # "percentage" or "fixed"
    discountValue: int
    eventId: Optional[str] = None
    description: Optional[str] = None
    currency: str = "USD"
    applicableTicketTypeIds: Optional[List[str]] = None
    maxUses: Optional[int] = None
    maxUsesPerUser: int = 1
    minimumOrderAmount: Optional[int] = None  # In cents
    minimumTickets: Optional[int] = None
    minOrderAmount: Optional[int] = None  # Legacy - kept for compatibility
    maxDiscountAmount: Optional[int] = None
    validFrom: Optional[datetime] = None
    validUntil: Optional[datetime] = None
    isActive: bool = True


# Alias for frontend compatibility
CreatePromoCodeInput = PromoCodeCreateInput


@strawberry.input
class PromoCodeUpdateInput:
    """Input for updating a promo code."""
    description: Optional[str] = None
    discountType: Optional[str] = None
    discountValue: Optional[int] = None
    currency: Optional[str] = None
    applicableTicketTypeIds: Optional[List[str]] = None
    maxUses: Optional[int] = None
    maxUsesPerUser: Optional[int] = None
    minimumOrderAmount: Optional[int] = None
    minimumTickets: Optional[int] = None
    validFrom: Optional[datetime] = None
    validUntil: Optional[datetime] = None
    isActive: Optional[bool] = None