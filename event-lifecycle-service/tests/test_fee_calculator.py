"""
Tests for the platform fee calculator.

Verifies that FeeCalculator correctly:
- Calculates per-ticket percentage + fixed fees
- Handles free tickets (zero price) with no fees
- Uses math.ceil rounding (always rounds up)
- Supports org-specific fee overrides
- Supports absorption models (absorb vs pass_to_buyer)
- Produces correct FeeBreakdown structures
"""

import pytest
from unittest.mock import MagicMock

from app.services.payment.fee_calculator import (
    FeeCalculator,
    OrderItemData,
    FeeBreakdown,
    ItemFee,
)


class TestFeeCalculator:
    """Tests for the platform fee calculator."""

    def setup_method(self):
        """Create a calculator with default 4% + $0.75 fees."""
        self.calculator = FeeCalculator(default_percent=4.0, default_fixed_cents=75)

    # ------------------------------------------------------------------ #
    # Basic calculations
    # ------------------------------------------------------------------ #

    def test_single_ticket_fee_calculation(self):
        """$50 ticket: 4% ($2.00) + $0.75 = $2.75 per ticket (275 cents)."""
        items = [OrderItemData(ticket_type_name="GA", quantity=1, unit_price=5000)]
        result = self.calculator.calculate_order_fees(items)

        assert result.platform_fee_total == 275
        assert len(result.per_item_fees) == 1
        assert result.per_item_fees[0].fee_per_ticket == 275
        assert result.per_item_fees[0].fee_subtotal == 275

    def test_multiple_tickets_same_type(self):
        """3x $50 tickets = $2.75 * 3 = $8.25 total fee (825 cents)."""
        items = [OrderItemData(ticket_type_name="GA", quantity=3, unit_price=5000)]
        result = self.calculator.calculate_order_fees(items)

        assert result.platform_fee_total == 825
        assert result.per_item_fees[0].fee_per_ticket == 275
        assert result.per_item_fees[0].fee_subtotal == 825
        assert result.per_item_fees[0].quantity == 3

    def test_multiple_ticket_types(self):
        """Mix of ticket types, each calculated independently."""
        items = [
            OrderItemData(ticket_type_name="GA", quantity=2, unit_price=5000),
            OrderItemData(ticket_type_name="VIP", quantity=1, unit_price=10000),
        ]
        result = self.calculator.calculate_order_fees(items)

        # GA: ceil(5000 * 4/100) = 200 + 75 = 275 per ticket, 275 * 2 = 550
        # VIP: ceil(10000 * 4/100) = 400 + 75 = 475 per ticket, 475 * 1 = 475
        assert len(result.per_item_fees) == 2
        assert result.per_item_fees[0].fee_per_ticket == 275
        assert result.per_item_fees[0].fee_subtotal == 550
        assert result.per_item_fees[1].fee_per_ticket == 475
        assert result.per_item_fees[1].fee_subtotal == 475
        assert result.platform_fee_total == 550 + 475

    def test_free_ticket_no_fee(self):
        """$0 tickets should have zero fees."""
        items = [OrderItemData(ticket_type_name="Free", quantity=5, unit_price=0)]
        result = self.calculator.calculate_order_fees(items)

        assert result.platform_fee_total == 0
        assert result.per_item_fees[0].fee_per_ticket == 0
        assert result.per_item_fees[0].fee_subtotal == 0

    def test_mixed_free_and_paid_tickets(self):
        """Only paid tickets get fees, free ones are skipped."""
        items = [
            OrderItemData(ticket_type_name="Free", quantity=2, unit_price=0),
            OrderItemData(ticket_type_name="Paid", quantity=1, unit_price=5000),
        ]
        result = self.calculator.calculate_order_fees(items)

        assert result.per_item_fees[0].fee_per_ticket == 0
        assert result.per_item_fees[0].fee_subtotal == 0
        assert result.per_item_fees[1].fee_per_ticket == 275
        assert result.per_item_fees[1].fee_subtotal == 275
        assert result.platform_fee_total == 275

    # ------------------------------------------------------------------ #
    # Rounding
    # ------------------------------------------------------------------ #

    def test_rounding_up_percentage(self):
        """$33 ticket: 4% = 132 cents (exact), ceil = 132. Fee = 132 + 75 = 207 cents."""
        items = [OrderItemData(ticket_type_name="GA", quantity=1, unit_price=3300)]
        result = self.calculator.calculate_order_fees(items)

        # ceil(3300 * 4 / 100) = ceil(132.0) = 132
        assert result.per_item_fees[0].fee_per_ticket == 132 + 75
        assert result.platform_fee_total == 207

    def test_rounding_up_fractional_percentage(self):
        """$33.33 ticket (3333 cents): 4% = 133.32, ceil = 134. Fee = 134 + 75 = 209."""
        items = [OrderItemData(ticket_type_name="GA", quantity=1, unit_price=3333)]
        result = self.calculator.calculate_order_fees(items)

        # ceil(3333 * 4 / 100) = ceil(133.32) = 134
        assert result.per_item_fees[0].fee_per_ticket == 134 + 75
        assert result.platform_fee_total == 209

    def test_small_ticket_rounding(self):
        """$1 ticket (100 cents): 4% = 4 cents + 75 = 79 cents."""
        items = [OrderItemData(ticket_type_name="Budget", quantity=1, unit_price=100)]
        result = self.calculator.calculate_order_fees(items)

        # ceil(100 * 4 / 100) = ceil(4.0) = 4
        assert result.per_item_fees[0].fee_per_ticket == 79
        assert result.platform_fee_total == 79

    # ------------------------------------------------------------------ #
    # Absorption models
    # ------------------------------------------------------------------ #

    def test_absorb_model_buyer_pays_subtotal(self):
        """In absorb model, buyer total = subtotal (no fee added)."""
        buyer_total = self.calculator.calculate_buyer_total(
            subtotal=5000,
            platform_fee_total=275,
            absorption_model="absorb",
        )
        assert buyer_total == 5000

    def test_pass_to_buyer_model_adds_fee(self):
        """In pass_to_buyer model, buyer total = subtotal + platform_fee."""
        buyer_total = self.calculator.calculate_buyer_total(
            subtotal=5000,
            platform_fee_total=275,
            absorption_model="pass_to_buyer",
        )
        assert buyer_total == 5275

    def test_absorb_is_default_model(self):
        """When no org settings provided, absorption model defaults to 'absorb'."""
        items = [OrderItemData(ticket_type_name="GA", quantity=1, unit_price=5000)]
        result = self.calculator.calculate_order_fees(items)
        assert result.absorption_model == "absorb"

    def test_pass_to_buyer_via_org_settings(self):
        """Org settings with fee_absorption='pass_to_buyer' propagates to breakdown."""
        org_settings = MagicMock()
        org_settings.platform_fee_percent = None
        org_settings.platform_fee_fixed = None
        org_settings.fee_absorption = "pass_to_buyer"

        items = [OrderItemData(ticket_type_name="GA", quantity=1, unit_price=5000)]
        result = self.calculator.calculate_order_fees(items, org_settings=org_settings)
        assert result.absorption_model == "pass_to_buyer"

    # ------------------------------------------------------------------ #
    # Org overrides
    # ------------------------------------------------------------------ #

    def test_org_override_percent(self):
        """Organization with custom 2.5% fee instead of default 4%."""
        org_settings = MagicMock()
        org_settings.platform_fee_percent = 2.5
        org_settings.platform_fee_fixed = None
        org_settings.fee_absorption = "absorb"

        items = [OrderItemData(ticket_type_name="GA", quantity=1, unit_price=5000)]
        result = self.calculator.calculate_order_fees(items, org_settings=org_settings)

        # ceil(5000 * 2.5 / 100) = ceil(125.0) = 125 + 75 (default fixed) = 200
        assert result.fee_percent_used == 2.5
        assert result.fee_fixed_used == 75  # Default fixed since override is None
        assert result.per_item_fees[0].fee_per_ticket == 200

    def test_org_override_fixed(self):
        """Organization with custom $0.50 (50 cents) fixed fee instead of $0.75."""
        org_settings = MagicMock()
        org_settings.platform_fee_percent = None
        org_settings.platform_fee_fixed = 50
        org_settings.fee_absorption = "absorb"

        items = [OrderItemData(ticket_type_name="GA", quantity=1, unit_price=5000)]
        result = self.calculator.calculate_order_fees(items, org_settings=org_settings)

        # ceil(5000 * 4 / 100) = 200 + 50 (custom fixed) = 250
        assert result.fee_percent_used == 4.0  # Default percent since override is None
        assert result.fee_fixed_used == 50
        assert result.per_item_fees[0].fee_per_ticket == 250

    def test_org_override_both(self):
        """Organization with both custom percent (2%) and fixed (50 cents)."""
        org_settings = MagicMock()
        org_settings.platform_fee_percent = 2.0
        org_settings.platform_fee_fixed = 50
        org_settings.fee_absorption = "absorb"

        items = [OrderItemData(ticket_type_name="GA", quantity=1, unit_price=5000)]
        result = self.calculator.calculate_order_fees(items, org_settings=org_settings)

        # ceil(5000 * 2 / 100) = 100 + 50 = 150
        assert result.fee_percent_used == 2.0
        assert result.fee_fixed_used == 50
        assert result.per_item_fees[0].fee_per_ticket == 150
        assert result.platform_fee_total == 150

    def test_org_settings_none_uses_defaults(self):
        """When org_settings is None, use default rates."""
        items = [OrderItemData(ticket_type_name="GA", quantity=1, unit_price=5000)]
        result = self.calculator.calculate_order_fees(items, org_settings=None)

        assert result.fee_percent_used == 4.0
        assert result.fee_fixed_used == 75
        assert result.per_item_fees[0].fee_per_ticket == 275

    # ------------------------------------------------------------------ #
    # Edge cases
    # ------------------------------------------------------------------ #

    def test_empty_order_items(self):
        """Empty list returns zero fees."""
        result = self.calculator.calculate_order_fees([])

        assert result.platform_fee_total == 0
        assert result.per_item_fees == []

    def test_very_expensive_ticket(self):
        """$10,000 ticket (1_000_000 cents) calculates correctly."""
        items = [OrderItemData(ticket_type_name="Platinum", quantity=1, unit_price=1_000_000)]
        result = self.calculator.calculate_order_fees(items)

        # ceil(1000000 * 4 / 100) = 40000 + 75 = 40075
        assert result.per_item_fees[0].fee_per_ticket == 40075
        assert result.platform_fee_total == 40075

    def test_one_cent_ticket(self):
        """$0.01 ticket (1 cent): smallest possible paid ticket."""
        items = [OrderItemData(ticket_type_name="Penny", quantity=1, unit_price=1)]
        result = self.calculator.calculate_order_fees(items)

        # ceil(1 * 4 / 100) = ceil(0.04) = 1 + 75 = 76
        assert result.per_item_fees[0].fee_per_ticket == 76
        assert result.platform_fee_total == 76

    def test_negative_price_treated_as_free(self):
        """Negative price (edge case) should be treated same as free -- no fees."""
        items = [OrderItemData(ticket_type_name="Weird", quantity=1, unit_price=-100)]
        result = self.calculator.calculate_order_fees(items)

        assert result.per_item_fees[0].fee_per_ticket == 0
        assert result.platform_fee_total == 0

    # ------------------------------------------------------------------ #
    # Fee breakdown structure
    # ------------------------------------------------------------------ #

    def test_fee_breakdown_has_correct_fields(self):
        """Verify FeeBreakdown dataclass has all expected fields."""
        items = [OrderItemData(ticket_type_name="GA", quantity=1, unit_price=5000)]
        result = self.calculator.calculate_order_fees(items)

        assert isinstance(result, FeeBreakdown)
        assert hasattr(result, "platform_fee_total")
        assert hasattr(result, "per_item_fees")
        assert hasattr(result, "fee_percent_used")
        assert hasattr(result, "fee_fixed_used")
        assert hasattr(result, "absorption_model")

    def test_item_fee_has_correct_fields(self):
        """Verify ItemFee dataclass has all expected fields."""
        items = [OrderItemData(ticket_type_name="GA", quantity=2, unit_price=5000)]
        result = self.calculator.calculate_order_fees(items)

        item_fee = result.per_item_fees[0]
        assert isinstance(item_fee, ItemFee)
        assert item_fee.ticket_type_name == "GA"
        assert item_fee.quantity == 2
        assert item_fee.unit_price == 5000
        assert item_fee.fee_per_ticket == 275
        assert item_fee.fee_subtotal == 550

    def test_per_item_fees_match_total(self):
        """Sum of per_item_fees.fee_subtotal == platform_fee_total."""
        items = [
            OrderItemData(ticket_type_name="GA", quantity=3, unit_price=2500),
            OrderItemData(ticket_type_name="VIP", quantity=2, unit_price=7500),
            OrderItemData(ticket_type_name="Free", quantity=5, unit_price=0),
        ]
        result = self.calculator.calculate_order_fees(items)

        calculated_total = sum(item.fee_subtotal for item in result.per_item_fees)
        assert calculated_total == result.platform_fee_total

    def test_custom_default_rates(self):
        """Calculator with custom default rates works correctly."""
        calculator = FeeCalculator(default_percent=5.0, default_fixed_cents=100)
        items = [OrderItemData(ticket_type_name="GA", quantity=1, unit_price=10000)]
        result = calculator.calculate_order_fees(items)

        # ceil(10000 * 5 / 100) = 500 + 100 = 600
        assert result.fee_percent_used == 5.0
        assert result.fee_fixed_used == 100
        assert result.per_item_fees[0].fee_per_ticket == 600
        assert result.platform_fee_total == 600

    def test_zero_percent_fee(self):
        """Calculator with 0% fee still applies fixed fee."""
        calculator = FeeCalculator(default_percent=0.0, default_fixed_cents=75)
        items = [OrderItemData(ticket_type_name="GA", quantity=1, unit_price=5000)]
        result = calculator.calculate_order_fees(items)

        # ceil(5000 * 0 / 100) = 0 + 75 = 75
        assert result.per_item_fees[0].fee_per_ticket == 75

    def test_zero_fixed_fee(self):
        """Calculator with $0 fixed fee applies only percentage."""
        calculator = FeeCalculator(default_percent=4.0, default_fixed_cents=0)
        items = [OrderItemData(ticket_type_name="GA", quantity=1, unit_price=5000)]
        result = calculator.calculate_order_fees(items)

        # ceil(5000 * 4 / 100) = 200 + 0 = 200
        assert result.per_item_fees[0].fee_per_ticket == 200
