# app/services/ticket_management/ticket_service.py
"""
Ticket Management Service

Handles business logic for:
- Ticket type management
- Promo code validation
- Ticket generation after payment
- Inventory management
- Check-in operations
"""

import logging
from typing import List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.models.ticket_type import TicketType
from app.models.promo_code import PromoCode
from app.models.ticket import Ticket
from app.models.order import Order
from app.models.order_item import OrderItem
from app.crud.ticket_type_v2 import ticket_type_crud
from app.crud.promo_code_crud import promo_code_crud
from app.crud.ticket_crud import ticket_crud
from app.schemas.ticket_management import (
    TicketTypeCreate,
    TicketTypeUpdate,
    TicketTypeResponse,
    TicketTypeStats,
    PromoCodeCreate,
    PromoCodeUpdate,
    PromoCodeValidation,
    Money,
    CartItem,
    EventTicketSummary,
    DiscountType,
)

logger = logging.getLogger(__name__)


class TicketManagementService:
    """Service for managing tickets, ticket types, and promo codes."""

    # ========================================
    # Ticket Type Operations
    # ========================================

    def get_ticket_types_for_event(
        self,
        db: Session,
        event_id: str,
        include_inactive: bool = False,
        include_hidden: bool = False
    ) -> List[TicketType]:
        """Get all ticket types for an event."""
        return ticket_type_crud.get_by_event(
            db, event_id, include_inactive, include_hidden
        )

    def get_available_ticket_types(
        self,
        db: Session,
        event_id: str
    ) -> List[TicketType]:
        """Get ticket types available for purchase."""
        return ticket_type_crud.get_available_for_purchase(db, event_id)

    def create_ticket_type(
        self,
        db: Session,
        input_data: TicketTypeCreate,
        organization_id: str,
        user_id: Optional[str] = None
    ) -> TicketType:
        """Create a new ticket type."""
        return ticket_type_crud.create(
            db, input_data, organization_id, user_id
        )

    def update_ticket_type(
        self,
        db: Session,
        ticket_type_id: str,
        input_data: TicketTypeUpdate
    ) -> Optional[TicketType]:
        """Update a ticket type."""
        return ticket_type_crud.update(db, ticket_type_id, input_data)

    def delete_ticket_type(
        self,
        db: Session,
        ticket_type_id: str
    ) -> bool:
        """Delete a ticket type (only if no sales)."""
        return ticket_type_crud.delete(db, ticket_type_id)

    def reorder_ticket_types(
        self,
        db: Session,
        event_id: str,
        ticket_type_ids: List[str]
    ) -> List[TicketType]:
        """Reorder ticket types for an event."""
        return ticket_type_crud.reorder(db, event_id, ticket_type_ids)

    def duplicate_ticket_type(
        self,
        db: Session,
        ticket_type_id: str,
        user_id: Optional[str] = None
    ) -> Optional[TicketType]:
        """Duplicate a ticket type."""
        return ticket_type_crud.duplicate(db, ticket_type_id, user_id)

    # ========================================
    # Promo Code Operations
    # ========================================

    def get_promo_codes_for_event(
        self,
        db: Session,
        event_id: str,
        include_inactive: bool = False
    ) -> List[PromoCode]:
        """Get all promo codes for an event."""
        return promo_code_crud.get_by_event(db, event_id, include_inactive)

    def get_organization_promo_codes(
        self,
        db: Session,
        organization_id: str,
        org_wide_only: bool = True
    ) -> List[PromoCode]:
        """Get organization-wide promo codes."""
        return promo_code_crud.get_by_organization(
            db, organization_id, org_wide_only
        )

    def create_promo_code(
        self,
        db: Session,
        input_data: PromoCodeCreate,
        organization_id: str,
        user_id: Optional[str] = None
    ) -> PromoCode:
        """Create a new promo code."""
        return promo_code_crud.create(
            db, input_data, organization_id, user_id
        )

    def update_promo_code(
        self,
        db: Session,
        promo_code_id: str,
        input_data: PromoCodeUpdate
    ) -> Optional[PromoCode]:
        """Update a promo code."""
        return promo_code_crud.update(db, promo_code_id, input_data)

    def delete_promo_code(
        self,
        db: Session,
        promo_code_id: str
    ) -> bool:
        """Delete a promo code."""
        return promo_code_crud.delete(db, promo_code_id)

    def deactivate_promo_code(
        self,
        db: Session,
        promo_code_id: str
    ) -> Optional[PromoCode]:
        """Deactivate a promo code (soft disable)."""
        return promo_code_crud.deactivate(db, promo_code_id)

    def validate_promo_code(
        self,
        db: Session,
        code: str,
        event_id: str,
        organization_id: str,
        cart_items: List[CartItem],
        user_id: Optional[str] = None,
        guest_email: Optional[str] = None
    ) -> PromoCodeValidation:
        """Validate a promo code for a cart."""
        # 1. Find the promo code
        promo_code = promo_code_crud.get_by_code(
            db, code, organization_id, event_id
        )

        if not promo_code:
            return PromoCodeValidation(
                is_valid=False,
                error_code="NOT_FOUND",
                error_message="Invalid promo code"
            )

        # 2. Check if active
        if not promo_code.is_active:
            return PromoCodeValidation(
                is_valid=False,
                error_code="INACTIVE",
                error_message="This code is no longer active"
            )

        # 3. Check validity period
        now = datetime.now(timezone.utc)
        if promo_code.valid_from and now < promo_code.valid_from:
            return PromoCodeValidation(
                is_valid=False,
                error_code="NOT_YET_VALID",
                error_message="This code is not yet valid"
            )

        if promo_code.valid_until and now > promo_code.valid_until:
            return PromoCodeValidation(
                is_valid=False,
                error_code="EXPIRED",
                error_message="This code has expired"
            )

        # 4. Check usage limits
        if promo_code.max_uses is not None and promo_code.current_uses >= promo_code.max_uses:
            return PromoCodeValidation(
                is_valid=False,
                error_code="MAX_USES",
                error_message="This code has reached its usage limit"
            )

        # 5. Check per-user usage
        user_usage_count = promo_code_crud.get_user_usage_count(
            db, promo_code.id, user_id, guest_email
        )

        if user_usage_count >= promo_code.max_uses_per_user:
            return PromoCodeValidation(
                is_valid=False,
                error_code="USER_LIMIT",
                error_message="You have already used this code"
            )

        # 6. Check applicable ticket types
        applicable_items = []
        for item in cart_items:
            if not promo_code.applicable_ticket_type_ids:
                # Applies to all
                applicable_items.append(item)
            elif item.ticket_type_id in promo_code.applicable_ticket_type_ids:
                applicable_items.append(item)

        if not applicable_items:
            return PromoCodeValidation(
                is_valid=False,
                error_code="NOT_APPLICABLE",
                error_message="This code does not apply to your selected tickets"
            )

        # 7. Calculate discount
        applicable_subtotal = sum(item.price * item.quantity for item in applicable_items)
        total_quantity = sum(item.quantity for item in cart_items)
        cart_total = sum(item.price * item.quantity for item in cart_items)

        if promo_code.discount_type == "percentage":
            discount_amount = int(applicable_subtotal * promo_code.discount_value / 100)
        else:  # fixed
            discount_amount = min(promo_code.discount_value, applicable_subtotal)

        # 8. Check minimum requirements
        min_tickets = promo_code.minimum_tickets or 1
        if total_quantity < min_tickets:
            return PromoCodeValidation(
                is_valid=False,
                error_code="MIN_TICKETS",
                error_message=f"Minimum {min_tickets} tickets required"
            )

        min_amount = promo_code.minimum_order_amount or promo_code.min_order_amount
        if min_amount and cart_total < min_amount:
            return PromoCodeValidation(
                is_valid=False,
                error_code="MIN_AMOUNT",
                error_message=f"Minimum order of ${min_amount / 100:.2f} required"
            )

        # Build response
        from app.schemas.ticket_management import PromoCodeResponse

        return PromoCodeValidation(
            is_valid=True,
            promo_code=PromoCodeResponse(
                id=promo_code.id,
                event_id=promo_code.event_id,
                organization_id=promo_code.organization_id,
                code=promo_code.code,
                description=promo_code.description,
                discount_type=DiscountType(promo_code.discount_type),
                discount_value=promo_code.discount_value,
                discount_formatted=promo_code.discount_formatted,
                applicable_ticket_type_ids=promo_code.applicable_ticket_type_ids,
                max_uses=promo_code.max_uses,
                max_uses_per_user=promo_code.max_uses_per_user,
                current_uses=promo_code.current_uses,
                remaining_uses=promo_code.remaining_uses,
                valid_from=promo_code.valid_from,
                valid_until=promo_code.valid_until,
                is_currently_valid=promo_code.is_currently_valid,
                minimum_order_amount=promo_code.minimum_order_amount,
                minimum_tickets=promo_code.minimum_tickets,
                is_active=promo_code.is_active,
                created_at=promo_code.created_at,
            ),
            discount_amount=Money(
                amount=discount_amount,
                currency=promo_code.currency or "USD"
            )
        )

    # ========================================
    # Inventory Management
    # ========================================

    def reserve_inventory(
        self,
        db: Session,
        items: List[dict]
    ) -> bool:
        """Reserve inventory for items (when checkout starts)."""
        try:
            for item in items:
                success = ticket_type_crud.reserve_inventory(
                    db, item["ticket_type_id"], item["quantity"]
                )
                if not success:
                    raise ValueError(
                        f"Insufficient inventory for ticket type {item['ticket_type_id']}"
                    )
            return True
        except Exception as e:
            logger.error(f"Failed to reserve inventory: {e}")
            raise

    def release_inventory(
        self,
        db: Session,
        items: List[dict]
    ) -> bool:
        """Release reserved inventory (when order expires/cancelled)."""
        for item in items:
            ticket_type_crud.release_reservation(
                db, item["ticket_type_id"], item["quantity"]
            )
        return True

    def confirm_inventory_sale(
        self,
        db: Session,
        items: List[dict]
    ) -> bool:
        """Confirm sale of reserved inventory (after payment)."""
        for item in items:
            ticket_type_crud.confirm_sale(
                db, item["ticket_type_id"], item["quantity"]
            )
        return True

    # ========================================
    # Ticket Generation
    # ========================================

    def generate_tickets_for_order(
        self,
        db: Session,
        order: Order,
        order_items: List[OrderItem]
    ) -> List[Ticket]:
        """Generate tickets after successful payment."""
        tickets = []

        for item in order_items:
            # Generate one ticket per quantity
            for i in range(item.quantity):
                ticket = ticket_crud.create(
                    db,
                    order_id=order.id,
                    order_item_id=item.id,
                    ticket_type_id=item.ticket_type_id,
                    event_id=order.event_id,
                    attendee_name=order.customer_name,
                    attendee_email=order.customer_email,
                    user_id=order.user_id,
                )
                tickets.append(ticket)

            # Confirm the sale in inventory
            ticket_type_crud.confirm_sale(db, item.ticket_type_id, item.quantity)

        logger.info(f"Generated {len(tickets)} tickets for order {order.id}")
        return tickets

    # ========================================
    # Check-in Operations
    # ========================================

    def check_in_ticket(
        self,
        db: Session,
        ticket_code: str,
        event_id: str,
        staff_user_id: str,
        location: Optional[str] = None
    ) -> Ticket:
        """Check in a ticket by code, JWT QR data, or legacy pipe-delimited QR data.

        Handles three input formats:
        - JWT (v2): Signed token from QR scan -> verify signature, extract tcode
        - Legacy pipe-delimited (v1): "{id}|{code}|{event_id}|{hash}" -> extract code
        - Plain ticket code: "TKT-XXXXXX-XX" -> use directly
        """
        from app.services.ticket_management.qr_signing import (
            verify_ticket_qr,
            is_jwt_qr,
        )

        actual_ticket_code = ticket_code

        # If input looks like a JWT (from QR scan), verify signature and extract code
        if is_jwt_qr(ticket_code):
            claims = verify_ticket_qr(ticket_code)
            if not claims:
                raise ValueError("Invalid or expired QR code")
            if claims.get("eid") != event_id:
                raise ValueError("QR code is not for this event")
            actual_ticket_code = claims["tcode"]

        # If input looks like legacy pipe-delimited format, extract the ticket code
        elif "|" in ticket_code:
            parts = ticket_code.split("|")
            if len(parts) >= 2:
                actual_ticket_code = parts[1]

        ticket = ticket_crud.get_by_code(db, actual_ticket_code, event_id)

        if not ticket:
            raise ValueError("Ticket not found")

        if ticket.event_id != event_id:
            raise ValueError("Ticket is not for this event")

        return ticket_crud.check_in(db, ticket.id, staff_user_id, location)

    def reverse_check_in(
        self,
        db: Session,
        ticket_id: str
    ) -> Ticket:
        """Reverse a check-in."""
        return ticket_crud.reverse_check_in(db, ticket_id)

    # ========================================
    # Ticket Management
    # ========================================

    def cancel_ticket(
        self,
        db: Session,
        ticket_id: str,
        reason: Optional[str] = None
    ) -> Ticket:
        """Cancel a ticket."""
        return ticket_crud.cancel(db, ticket_id, reason)

    def transfer_ticket(
        self,
        db: Session,
        ticket_id: str,
        new_attendee_name: str,
        new_attendee_email: str,
        new_user_id: Optional[str] = None
    ) -> Ticket:
        """Transfer a ticket to a new attendee."""
        return ticket_crud.transfer(
            db, ticket_id, new_attendee_name, new_attendee_email, new_user_id
        )

    def get_user_tickets(
        self,
        db: Session,
        user_id: str,
        event_id: Optional[str] = None
    ) -> List[Ticket]:
        """Get all tickets for a user."""
        return ticket_crud.get_by_user(db, user_id, event_id)

    def get_event_tickets(
        self,
        db: Session,
        event_id: str,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Ticket], int]:
        """Get all tickets for an event with filtering."""
        return ticket_crud.get_by_event(
            db, event_id, status, search, limit, offset
        )

    # ========================================
    # Statistics & Reporting
    # ========================================

    def get_event_ticket_summary(
        self,
        db: Session,
        event_id: str
    ) -> EventTicketSummary:
        """Get comprehensive ticket sales summary for an event."""
        # Get all ticket types
        ticket_types = ticket_type_crud.get_by_event(
            db, event_id, include_inactive=True
        )

        # Calculate totals
        total_capacity = 0
        total_sold = 0
        total_revenue = 0
        has_unlimited = False
        ticket_type_stats = []

        for tt in ticket_types:
            if tt.quantity_total is None:
                has_unlimited = True
            else:
                total_capacity += tt.quantity_total

            total_sold += tt.quantity_sold
            revenue = tt.revenue
            total_revenue += revenue

            # Calculate percentage sold
            percentage_sold = None
            if tt.quantity_total:
                percentage_sold = round(tt.quantity_sold / tt.quantity_total * 100, 1)

            ticket_type_stats.append(TicketTypeStats(
                ticket_type_id=tt.id,
                ticket_type_name=tt.name,
                quantity_sold=tt.quantity_sold,
                quantity_available=tt.quantity_available,
                revenue=Money(amount=revenue, currency=tt.currency),
                percentage_sold=percentage_sold
            ))

        # Get sales stats
        sales_stats = ticket_crud.get_sales_stats(db, event_id)

        # Get currency from first ticket type or default
        currency = ticket_types[0].currency if ticket_types else "USD"

        # Calculate revenue by period based on average ticket price
        avg_price = total_revenue // total_sold if total_sold > 0 else 0
        revenue_today = avg_price * sales_stats["sales_today"]
        revenue_this_week = avg_price * sales_stats["sales_this_week"]
        revenue_this_month = avg_price * sales_stats["sales_this_month"]

        return EventTicketSummary(
            event_id=event_id,
            total_ticket_types=len(ticket_types),
            total_capacity=None if has_unlimited else total_capacity,
            total_sold=total_sold,
            total_revenue=Money(amount=total_revenue, currency=currency),
            ticket_type_stats=ticket_type_stats,
            sales_today=sales_stats["sales_today"],
            sales_this_week=sales_stats["sales_this_week"],
            sales_this_month=sales_stats["sales_this_month"],
            revenue_today=Money(amount=revenue_today, currency=currency),
            revenue_this_week=Money(amount=revenue_this_week, currency=currency),
            revenue_this_month=Money(amount=revenue_this_month, currency=currency),
        )


# Singleton instance
ticket_management_service = TicketManagementService()
