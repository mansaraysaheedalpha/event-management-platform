"""
Platform fee calculation for ticket orders.

Fee model:
- platform_fee = (ticket_price * fee_percent / 100) + fee_fixed
- Applied PER TICKET (not per order)
- Free tickets ($0) have no fees
- Supports org-specific fee overrides
- Supports two absorption models: absorb (organizer pays) and pass_to_buyer
"""

from dataclasses import dataclass
from typing import Optional
import math


@dataclass
class ItemFee:
    ticket_type_name: str
    quantity: int
    unit_price: int          # cents
    fee_per_ticket: int      # cents
    fee_subtotal: int        # cents (fee_per_ticket * quantity)


@dataclass
class FeeBreakdown:
    platform_fee_total: int          # Total platform fee in cents
    per_item_fees: list[ItemFee]     # Per-item breakdown
    fee_percent_used: float          # The percentage applied
    fee_fixed_used: int              # The fixed fee applied (cents)
    absorption_model: str            # "absorb" or "pass_to_buyer"


@dataclass
class OrderItemData:
    ticket_type_name: str
    quantity: int
    unit_price: int  # cents


class FeeCalculator:
    """
    Calculates platform fees for ticket orders.

    Fee model:
    - platform_fee = (ticket_price * platform_fee_percent / 100) + platform_fee_fixed
    - Applied PER TICKET (not per order)
    - Free tickets ($0) have no fees

    Args:
        default_percent: Default platform fee percentage (e.g., 4.0 for 4%)
        default_fixed_cents: Default fixed fee per ticket in cents (e.g., 75 for $0.75)
    """

    def __init__(self, default_percent: float, default_fixed_cents: int):
        self.default_percent = default_percent
        self.default_fixed_cents = default_fixed_cents

    def calculate_order_fees(
        self,
        items: list[OrderItemData],
        org_settings=None,  # OrganizationPaymentSettings or None
    ) -> FeeBreakdown:
        """
        Calculate fees for an entire order.

        Uses org-specific overrides if available, otherwise defaults.
        Free tickets (unit_price=0) have no fees.
        Uses math.ceil for rounding (always round up in platform's favor).
        """
        # Determine fee rates from org settings or defaults
        fee_percent = (
            float(org_settings.platform_fee_percent)
            if (org_settings and org_settings.platform_fee_percent is not None)
            else self.default_percent
        )
        fee_fixed = (
            int(org_settings.platform_fee_fixed)
            if (org_settings and org_settings.platform_fee_fixed is not None)
            else self.default_fixed_cents
        )
        absorption = (
            org_settings.fee_absorption
            if (org_settings and org_settings.fee_absorption)
            else "absorb"
        )

        per_item_fees = []
        total_fee = 0

        for item in items:
            if item.unit_price <= 0:
                # Free tickets have no fees
                per_item_fees.append(ItemFee(
                    ticket_type_name=item.ticket_type_name,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    fee_per_ticket=0,
                    fee_subtotal=0,
                ))
                continue

            # Calculate per-ticket fee: percentage of price + fixed fee
            percentage_component = math.ceil(item.unit_price * fee_percent / 100)
            fee_per_ticket = percentage_component + fee_fixed
            fee_subtotal = fee_per_ticket * item.quantity

            per_item_fees.append(ItemFee(
                ticket_type_name=item.ticket_type_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                fee_per_ticket=fee_per_ticket,
                fee_subtotal=fee_subtotal,
            ))
            total_fee += fee_subtotal

        return FeeBreakdown(
            platform_fee_total=total_fee,
            per_item_fees=per_item_fees,
            fee_percent_used=fee_percent,
            fee_fixed_used=fee_fixed,
            absorption_model=absorption,
        )

    def calculate_buyer_total(
        self,
        subtotal: int,
        platform_fee_total: int,
        absorption_model: str,
    ) -> int:
        """
        Calculate the total amount the buyer pays.

        If pass_to_buyer: buyer pays subtotal + platform_fee
        If absorb: buyer pays subtotal only (fees deducted from organizer's share)
        """
        if absorption_model == "pass_to_buyer":
            return subtotal + platform_fee_total
        return subtotal
