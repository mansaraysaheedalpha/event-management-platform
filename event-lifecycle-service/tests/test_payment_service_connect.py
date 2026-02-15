"""
Tests for Stripe Connect integration in PaymentService.

Verifies that PaymentService correctly:
- Gates paid ticket purchases behind Stripe Connect status checks
- Allows free ticket orders to bypass Connect gating entirely
- Calculates fees and stores fee breakdown in orders
- Passes connected_account_id and platform_fee_amount to payment intent params
- Respects absorption models (absorb vs pass_to_buyer) for buyer totals
- Sends refund confirmation emails on successful refunds
- Handles refunds for orders with connected accounts

All external dependencies (crud, providers, fee_calculator, DB) are mocked --
no real Stripe calls or database operations are ever made.
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, ANY
from datetime import datetime, timezone

from app.services.payment.payment_service import PaymentService
from app.schemas.payment import (
    CreateOrderInput,
    OrderItemCreate,
    InitiateRefundInput,
    RefundReason,
    RefundStatus,
)
from app.services.payment.fee_calculator import FeeBreakdown, ItemFee
from app.services.payment.provider_interface import (
    PaymentIntentResult,
    PaymentIntentStatusEnum,
    RefundResult,
    RefundStatusEnum,
)


def run_async(coro):
    """Helper to run async coroutines in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_org_settings(**overrides):
    """Create a mock OrganizationPaymentSettings object."""
    defaults = {
        "id": "ops_abc123",
        "organization_id": "org_123",
        "provider_id": "prov_stripe",
        "connected_account_id": "acct_test123",
        "is_active": True,
        "charges_enabled": True,
        "payouts_enabled": True,
        "details_submitted": True,
        "platform_fee_percent": 4.0,
        "platform_fee_fixed": 75,
        "fee_absorption": "absorb",
        "verified_at": datetime.now(timezone.utc),
        "onboarding_completed_at": datetime.now(timezone.utc),
        "deauthorized_at": None,
        "requirements_json": {},
        "payout_schedule": "automatic",
        "country": "US",
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    for key, val in defaults.items():
        setattr(mock, key, val)
    return mock


def _make_ticket_type(**overrides):
    """Create a mock ticket type object."""
    defaults = {
        "id": "tt_ga_001",
        "event_id": "evt_123",
        "name": "General Admission",
        "description": "Standard entry ticket",
        "price": 5000,  # $50.00
        "currency": "USD",
        "min_per_order": 1,
        "max_per_order": 10,
        "quantity_total": 100,
        "quantity_sold": 0,
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    for key, val in defaults.items():
        setattr(mock, key, val)
    return mock


def _make_event(**overrides):
    """Create a mock event object."""
    defaults = {
        "id": "evt_123",
        "name": "Test Conference 2026",
        "organization_id": "org_123",
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    for key, val in defaults.items():
        setattr(mock, key, val)
    return mock


def _make_order(**overrides):
    """Create a mock order object."""
    defaults = {
        "id": "ord_abc123def456",
        "order_number": "ORD-2026-A1B2C3",
        "event_id": "evt_123",
        "organization_id": "org_123",
        "user_id": "user_456",
        "guest_email": "buyer@example.com",
        "customer_name": "John Doe",
        "status": "completed",
        "subtotal": 5000,
        "discount_amount": 0,
        "tax_amount": 0,
        "platform_fee": 275,
        "total_amount": 5000,
        "connected_account_id": "acct_test123",
        "fee_absorption": "absorb",
        "fee_breakdown_json": None,
        "currency": "USD",
        "payment_provider": "stripe",
        "payment_intent_id": "pi_test123",
        "promo_code_id": None,
        "items": [],
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    for key, val in defaults.items():
        setattr(mock, key, val)
    return mock


def _make_payment(**overrides):
    """Create a mock payment object."""
    defaults = {
        "id": "pay_abc123",
        "order_id": "ord_abc123def456",
        "organization_id": "org_123",
        "provider_code": "stripe",
        "provider_payment_id": "pi_test123",
        "provider_intent_id": "pi_test123",
        "status": "succeeded",
        "amount": 5000,
        "amount_refunded": 0,
        "currency": "USD",
        "refundable_amount": 5000,
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    for key, val in defaults.items():
        setattr(mock, key, val)
    return mock


def _make_checkout_input(**overrides):
    """Create a CreateOrderInput for a single GA ticket."""
    defaults = {
        "event_id": "evt_123",
        "items": [OrderItemCreate(ticket_type_id="tt_ga_001", quantity=1)],
        "promo_code": None,
        "guest_email": "buyer@example.com",
        "guest_first_name": "John",
        "guest_last_name": "Doe",
        "guest_phone": None,
    }
    defaults.update(overrides)
    return CreateOrderInput(**defaults)


def _make_fee_breakdown(**overrides):
    """Create a FeeBreakdown for a standard $50 GA ticket."""
    defaults = {
        "platform_fee_total": 275,
        "fee_percent_used": 4.0,
        "fee_fixed_used": 75,
        "absorption_model": "absorb",
        "per_item_fees": [
            ItemFee(
                ticket_type_name="General Admission",
                quantity=1,
                unit_price=5000,
                fee_per_ticket=275,
                fee_subtotal=275,
            )
        ],
    }
    defaults.update(overrides)
    return FeeBreakdown(**defaults)


# ================================================================== #
# Patches applied to every test in this module
# ================================================================== #

# We patch crud, provider_factory, and the module-level fee_calculator
# at the module path where they are imported by payment_service.
_CRUD_PATCH = "app.services.payment.payment_service.crud"
_PROVIDER_FACTORY_PATCH = (
    "app.services.payment.payment_service.get_provider_for_currency"
)
_FEE_CALC_PATCH = "app.services.payment.payment_service.fee_calculator"
_ORDER_MODEL_PATCH = "app.services.payment.payment_service.Order"


class TestConnectGating:
    """
    Verify that create_checkout_session enforces Stripe Connect requirements
    for paid tickets and allows free tickets through without gating.
    """

    def setup_method(self):
        """Set up a PaymentService with a mocked DB session."""
        self.mock_db = MagicMock()
        self.service = PaymentService(self.mock_db)

    @patch(_ORDER_MODEL_PATCH)
    @patch(_FEE_CALC_PATCH)
    @patch(_PROVIDER_FACTORY_PATCH)
    @patch(_CRUD_PATCH)
    def test_raises_when_no_org_settings_for_paid_ticket(
        self, mock_crud, mock_provider_factory, mock_fee_calc, mock_order_model
    ):
        """Paid ticket checkout fails when no OrganizationPaymentSettings exist."""
        event = _make_event()
        ticket = _make_ticket_type(price=5000)

        mock_crud.event.get.return_value = event
        mock_crud.ticket_type.get.return_value = ticket
        mock_crud.ticket_type.is_available.return_value = True

        # No org_settings found in DB
        self.mock_db.query.return_value.filter.return_value.first.return_value = None

        input_data = _make_checkout_input()

        with pytest.raises(ValueError, match="not connected their payment account"):
            run_async(
                self.service.create_checkout_session(
                    input_data=input_data,
                    organization_id="org_123",
                )
            )

    @patch(_ORDER_MODEL_PATCH)
    @patch(_FEE_CALC_PATCH)
    @patch(_PROVIDER_FACTORY_PATCH)
    @patch(_CRUD_PATCH)
    def test_raises_when_connected_account_id_is_none(
        self, mock_crud, mock_provider_factory, mock_fee_calc, mock_order_model
    ):
        """Paid ticket checkout fails when org_settings exists but connected_account_id is None."""
        event = _make_event()
        ticket = _make_ticket_type(price=5000)

        mock_crud.event.get.return_value = event
        mock_crud.ticket_type.get.return_value = ticket
        mock_crud.ticket_type.is_available.return_value = True

        # Org settings exist but without a connected account
        org_settings = _make_org_settings(connected_account_id=None)
        self.mock_db.query.return_value.filter.return_value.first.return_value = (
            org_settings
        )

        input_data = _make_checkout_input()

        with pytest.raises(ValueError, match="not connected their payment account"):
            run_async(
                self.service.create_checkout_session(
                    input_data=input_data,
                    organization_id="org_123",
                )
            )

    @patch(_ORDER_MODEL_PATCH)
    @patch(_FEE_CALC_PATCH)
    @patch(_PROVIDER_FACTORY_PATCH)
    @patch(_CRUD_PATCH)
    def test_raises_when_charges_not_enabled(
        self, mock_crud, mock_provider_factory, mock_fee_calc, mock_order_model
    ):
        """Paid ticket checkout fails when org's charges_enabled is False."""
        event = _make_event()
        ticket = _make_ticket_type(price=5000)

        mock_crud.event.get.return_value = event
        mock_crud.ticket_type.get.return_value = ticket
        mock_crud.ticket_type.is_available.return_value = True

        # Org settings with connected account but charges not yet enabled
        org_settings = _make_org_settings(charges_enabled=False)
        self.mock_db.query.return_value.filter.return_value.first.return_value = (
            org_settings
        )

        input_data = _make_checkout_input()

        with pytest.raises(ValueError, match="payment account is under review"):
            run_async(
                self.service.create_checkout_session(
                    input_data=input_data,
                    organization_id="org_123",
                )
            )

    @patch(_ORDER_MODEL_PATCH)
    @patch(_FEE_CALC_PATCH)
    @patch(_PROVIDER_FACTORY_PATCH)
    @patch(_CRUD_PATCH)
    def test_free_ticket_bypasses_connect_gating(
        self, mock_crud, mock_provider_factory, mock_fee_calc, mock_order_model
    ):
        """Free ticket (total=0) skips all Connect checks and creates order."""
        event = _make_event()
        free_ticket = _make_ticket_type(id="tt_free_001", price=0, name="Free Entry")

        mock_crud.event.get.return_value = event
        mock_crud.ticket_type.get.return_value = free_ticket
        mock_crud.ticket_type.is_available.return_value = True
        mock_crud.ticket_type.reserve_quantity.return_value = True

        # No org settings at all -- should not matter for free tickets
        self.mock_db.query.return_value.filter.return_value.first.return_value = None

        # Create mock order for crud.order.create_order
        mock_order = _make_order(
            total_amount=0, subtotal=0, platform_fee=0, connected_account_id=None
        )
        mock_crud.order.create_order.return_value = mock_order
        mock_order_model.generate_order_number.return_value = "ORD-2026-FREE01"

        # Mock Order schema validation in the response building
        with patch("app.services.payment.payment_service.OrderSchema") as mock_schema:
            # Instead, we need to patch at the import location inside the method
            pass

        # The method does a late import: from app.schemas.payment import Order as OrderSchema
        with patch(
            "app.schemas.payment.Order.model_validate"
        ) as mock_validate:
            mock_validate.return_value = MagicMock()

            input_data = _make_checkout_input(
                items=[OrderItemCreate(ticket_type_id="tt_free_001", quantity=1)]
            )

            result = run_async(
                self.service.create_checkout_session(
                    input_data=input_data,
                    organization_id="org_123",
                )
            )

        # Free ticket: no payment intent should be created
        assert result.payment_intent is None
        # The DB query for OrganizationPaymentSettings should NOT have been called
        # (total_amount=0 skips the Connect gating block)
        mock_provider_factory.assert_not_called()
        mock_fee_calc.calculate_order_fees.assert_not_called()


class TestFeeCalculationIntegration:
    """
    Verify that fee breakdown is correctly calculated, stored in order,
    and passed to CreatePaymentIntentParams during checkout.
    """

    def setup_method(self):
        """Set up a PaymentService with a mocked DB session."""
        self.mock_db = MagicMock()
        self.service = PaymentService(self.mock_db)

    @patch(_ORDER_MODEL_PATCH)
    @patch(_FEE_CALC_PATCH)
    @patch(_PROVIDER_FACTORY_PATCH)
    @patch(_CRUD_PATCH)
    def test_fee_breakdown_stored_in_order(
        self, mock_crud, mock_provider_factory, mock_fee_calc, mock_order_model
    ):
        """Fee breakdown JSON is populated correctly in the created order."""
        event = _make_event()
        ticket = _make_ticket_type(price=5000)

        mock_crud.event.get.return_value = event
        mock_crud.ticket_type.get.return_value = ticket
        mock_crud.ticket_type.is_available.return_value = True
        mock_crud.ticket_type.reserve_quantity.return_value = True

        org_settings = _make_org_settings()
        self.mock_db.query.return_value.filter.return_value.first.return_value = (
            org_settings
        )

        # Set up fee calculator mock
        fee_breakdown = _make_fee_breakdown()
        mock_fee_calc.calculate_order_fees.return_value = fee_breakdown
        mock_fee_calc.calculate_buyer_total.return_value = 5000  # absorb model

        # Set up order creation mock
        mock_order = _make_order()
        mock_crud.order.create_order.return_value = mock_order
        mock_order_model.generate_order_number.return_value = "ORD-2026-A1B2C3"

        # Set up provider mock
        mock_provider = MagicMock()
        mock_provider.code = "stripe"
        mock_provider.get_publishable_key.return_value = "pk_test_fake"
        mock_provider.create_payment_intent = AsyncMock(
            return_value=PaymentIntentResult(
                intent_id="pi_test_new",
                client_secret="pi_test_new_secret",
                status=PaymentIntentStatusEnum.REQUIRES_PAYMENT_METHOD,
            )
        )
        mock_provider_factory.return_value = mock_provider

        with patch("app.schemas.payment.Order.model_validate") as mock_validate:
            mock_validate.return_value = MagicMock()

            input_data = _make_checkout_input()

            run_async(
                self.service.create_checkout_session(
                    input_data=input_data,
                    organization_id="org_123",
                    user_id="user_456",
                )
            )

        # Verify the order was created with correct fee breakdown
        create_call = mock_crud.order.create_order.call_args
        order_create_obj = create_call.kwargs.get("obj_in") or create_call[1].get("obj_in")

        assert order_create_obj.platform_fee == 275
        assert order_create_obj.fee_absorption == "absorb"
        assert order_create_obj.connected_account_id == "acct_test123"

        # Verify fee_breakdown_json structure
        fb_json = order_create_obj.fee_breakdown_json
        assert fb_json is not None
        assert fb_json["platform_fee_total"] == 275
        assert fb_json["fee_percent_used"] == 4.0
        assert fb_json["fee_fixed_used"] == 75
        assert fb_json["absorption_model"] == "absorb"
        assert len(fb_json["per_item_fees"]) == 1

        item_fee = fb_json["per_item_fees"][0]
        assert item_fee["ticket_type_name"] == "General Admission"
        assert item_fee["quantity"] == 1
        assert item_fee["unit_price"] == 5000
        assert item_fee["fee_per_ticket"] == 275
        assert item_fee["fee_subtotal"] == 275

    @patch(_ORDER_MODEL_PATCH)
    @patch(_FEE_CALC_PATCH)
    @patch(_PROVIDER_FACTORY_PATCH)
    @patch(_CRUD_PATCH)
    def test_platform_fee_and_connected_account_passed_to_payment_intent(
        self, mock_crud, mock_provider_factory, mock_fee_calc, mock_order_model
    ):
        """platform_fee_amount and connected_account_id are passed to CreatePaymentIntentParams."""
        event = _make_event()
        ticket = _make_ticket_type(price=5000)

        mock_crud.event.get.return_value = event
        mock_crud.ticket_type.get.return_value = ticket
        mock_crud.ticket_type.is_available.return_value = True
        mock_crud.ticket_type.reserve_quantity.return_value = True

        org_settings = _make_org_settings()
        self.mock_db.query.return_value.filter.return_value.first.return_value = (
            org_settings
        )

        fee_breakdown = _make_fee_breakdown()
        mock_fee_calc.calculate_order_fees.return_value = fee_breakdown
        mock_fee_calc.calculate_buyer_total.return_value = 5000

        mock_order = _make_order()
        mock_crud.order.create_order.return_value = mock_order
        mock_order_model.generate_order_number.return_value = "ORD-2026-A1B2C3"

        mock_provider = MagicMock()
        mock_provider.code = "stripe"
        mock_provider.get_publishable_key.return_value = "pk_test_fake"
        mock_provider.create_payment_intent = AsyncMock(
            return_value=PaymentIntentResult(
                intent_id="pi_test_new",
                client_secret="pi_test_new_secret",
                status=PaymentIntentStatusEnum.REQUIRES_PAYMENT_METHOD,
            )
        )
        mock_provider_factory.return_value = mock_provider

        with patch("app.schemas.payment.Order.model_validate") as mock_validate:
            mock_validate.return_value = MagicMock()

            input_data = _make_checkout_input()

            run_async(
                self.service.create_checkout_session(
                    input_data=input_data,
                    organization_id="org_123",
                    user_id="user_456",
                )
            )

        # Verify provider.create_payment_intent was called with correct params
        mock_provider.create_payment_intent.assert_called_once()
        call_args = mock_provider.create_payment_intent.call_args
        intent_params = call_args[0][0]  # First positional argument

        assert intent_params.connected_account_id == "acct_test123"
        assert intent_params.platform_fee_amount == 275
        assert intent_params.amount == 5000
        assert intent_params.currency == "USD"

    @patch(_ORDER_MODEL_PATCH)
    @patch(_FEE_CALC_PATCH)
    @patch(_PROVIDER_FACTORY_PATCH)
    @patch(_CRUD_PATCH)
    def test_absorb_model_buyer_total_equals_subtotal(
        self, mock_crud, mock_provider_factory, mock_fee_calc, mock_order_model
    ):
        """In absorb model, buyer_total = subtotal (fee not added to buyer's charge)."""
        event = _make_event()
        ticket = _make_ticket_type(price=5000)

        mock_crud.event.get.return_value = event
        mock_crud.ticket_type.get.return_value = ticket
        mock_crud.ticket_type.is_available.return_value = True
        mock_crud.ticket_type.reserve_quantity.return_value = True

        org_settings = _make_org_settings(fee_absorption="absorb")
        self.mock_db.query.return_value.filter.return_value.first.return_value = (
            org_settings
        )

        fee_breakdown = _make_fee_breakdown(absorption_model="absorb")
        mock_fee_calc.calculate_order_fees.return_value = fee_breakdown
        # Absorb model: buyer pays subtotal only
        mock_fee_calc.calculate_buyer_total.return_value = 5000

        mock_order = _make_order()
        mock_crud.order.create_order.return_value = mock_order
        mock_order_model.generate_order_number.return_value = "ORD-2026-A1B2C3"

        mock_provider = MagicMock()
        mock_provider.code = "stripe"
        mock_provider.get_publishable_key.return_value = "pk_test_fake"
        mock_provider.create_payment_intent = AsyncMock(
            return_value=PaymentIntentResult(
                intent_id="pi_test_new",
                client_secret="pi_test_new_secret",
                status=PaymentIntentStatusEnum.REQUIRES_PAYMENT_METHOD,
            )
        )
        mock_provider_factory.return_value = mock_provider

        with patch("app.schemas.payment.Order.model_validate") as mock_validate:
            mock_validate.return_value = MagicMock()

            input_data = _make_checkout_input()

            run_async(
                self.service.create_checkout_session(
                    input_data=input_data,
                    organization_id="org_123",
                )
            )

        # Verify buyer_total = subtotal (absorb model)
        create_call = mock_crud.order.create_order.call_args
        order_create_obj = create_call.kwargs.get("obj_in") or create_call[1].get("obj_in")
        assert order_create_obj.total_amount == 5000
        assert order_create_obj.fee_absorption == "absorb"

        # Verify payment intent uses buyer_total as the amount
        intent_params = mock_provider.create_payment_intent.call_args[0][0]
        assert intent_params.amount == 5000

    @patch(_ORDER_MODEL_PATCH)
    @patch(_FEE_CALC_PATCH)
    @patch(_PROVIDER_FACTORY_PATCH)
    @patch(_CRUD_PATCH)
    def test_pass_to_buyer_model_adds_fee_to_total(
        self, mock_crud, mock_provider_factory, mock_fee_calc, mock_order_model
    ):
        """In pass_to_buyer model, buyer_total = subtotal + platform_fee."""
        event = _make_event()
        ticket = _make_ticket_type(price=5000)

        mock_crud.event.get.return_value = event
        mock_crud.ticket_type.get.return_value = ticket
        mock_crud.ticket_type.is_available.return_value = True
        mock_crud.ticket_type.reserve_quantity.return_value = True

        org_settings = _make_org_settings(fee_absorption="pass_to_buyer")
        self.mock_db.query.return_value.filter.return_value.first.return_value = (
            org_settings
        )

        fee_breakdown = _make_fee_breakdown(absorption_model="pass_to_buyer")
        mock_fee_calc.calculate_order_fees.return_value = fee_breakdown
        # Pass-to-buyer model: buyer pays subtotal + fee
        mock_fee_calc.calculate_buyer_total.return_value = 5275  # 5000 + 275

        mock_order = _make_order()
        mock_crud.order.create_order.return_value = mock_order
        mock_order_model.generate_order_number.return_value = "ORD-2026-A1B2C3"

        mock_provider = MagicMock()
        mock_provider.code = "stripe"
        mock_provider.get_publishable_key.return_value = "pk_test_fake"
        mock_provider.create_payment_intent = AsyncMock(
            return_value=PaymentIntentResult(
                intent_id="pi_test_new",
                client_secret="pi_test_new_secret",
                status=PaymentIntentStatusEnum.REQUIRES_PAYMENT_METHOD,
            )
        )
        mock_provider_factory.return_value = mock_provider

        with patch("app.schemas.payment.Order.model_validate") as mock_validate:
            mock_validate.return_value = MagicMock()

            input_data = _make_checkout_input()

            run_async(
                self.service.create_checkout_session(
                    input_data=input_data,
                    organization_id="org_123",
                )
            )

        # Verify buyer_total = subtotal + fee (pass_to_buyer model)
        create_call = mock_crud.order.create_order.call_args
        order_create_obj = create_call.kwargs.get("obj_in") or create_call[1].get("obj_in")
        assert order_create_obj.total_amount == 5275
        assert order_create_obj.fee_absorption == "pass_to_buyer"

        # Verify payment intent uses the higher buyer_total
        intent_params = mock_provider.create_payment_intent.call_args[0][0]
        assert intent_params.amount == 5275

    @patch(_ORDER_MODEL_PATCH)
    @patch(_FEE_CALC_PATCH)
    @patch(_PROVIDER_FACTORY_PATCH)
    @patch(_CRUD_PATCH)
    def test_fee_calculator_called_with_correct_order_items(
        self, mock_crud, mock_provider_factory, mock_fee_calc, mock_order_model
    ):
        """fee_calculator.calculate_order_fees is called with OrderItemData from ticket types."""
        event = _make_event()
        ga_ticket = _make_ticket_type(
            id="tt_ga_001", price=5000, name="General Admission"
        )
        vip_ticket = _make_ticket_type(
            id="tt_vip_001", price=10000, name="VIP", currency="USD"
        )

        def get_ticket_type(db, id):
            if id == "tt_ga_001":
                return ga_ticket
            elif id == "tt_vip_001":
                return vip_ticket
            return None

        mock_crud.event.get.return_value = event
        mock_crud.ticket_type.get.side_effect = lambda db, id: get_ticket_type(db, id)
        mock_crud.ticket_type.is_available.return_value = True
        mock_crud.ticket_type.reserve_quantity.return_value = True

        org_settings = _make_org_settings()
        self.mock_db.query.return_value.filter.return_value.first.return_value = (
            org_settings
        )

        # Multi-item fee breakdown
        fee_breakdown = FeeBreakdown(
            platform_fee_total=1025,  # 275*2 + 475
            fee_percent_used=4.0,
            fee_fixed_used=75,
            absorption_model="absorb",
            per_item_fees=[
                ItemFee(
                    ticket_type_name="General Admission",
                    quantity=2,
                    unit_price=5000,
                    fee_per_ticket=275,
                    fee_subtotal=550,
                ),
                ItemFee(
                    ticket_type_name="VIP",
                    quantity=1,
                    unit_price=10000,
                    fee_per_ticket=475,
                    fee_subtotal=475,
                ),
            ],
        )
        mock_fee_calc.calculate_order_fees.return_value = fee_breakdown
        mock_fee_calc.calculate_buyer_total.return_value = 20000  # absorb

        mock_order = _make_order(subtotal=20000, total_amount=20000, platform_fee=1025)
        mock_crud.order.create_order.return_value = mock_order
        mock_order_model.generate_order_number.return_value = "ORD-2026-MULTI1"

        mock_provider = MagicMock()
        mock_provider.code = "stripe"
        mock_provider.get_publishable_key.return_value = "pk_test_fake"
        mock_provider.create_payment_intent = AsyncMock(
            return_value=PaymentIntentResult(
                intent_id="pi_multi",
                client_secret="pi_multi_secret",
                status=PaymentIntentStatusEnum.REQUIRES_PAYMENT_METHOD,
            )
        )
        mock_provider_factory.return_value = mock_provider

        with patch("app.schemas.payment.Order.model_validate") as mock_validate:
            mock_validate.return_value = MagicMock()

            input_data = _make_checkout_input(
                items=[
                    OrderItemCreate(ticket_type_id="tt_ga_001", quantity=2),
                    OrderItemCreate(ticket_type_id="tt_vip_001", quantity=1),
                ]
            )

            run_async(
                self.service.create_checkout_session(
                    input_data=input_data,
                    organization_id="org_123",
                )
            )

        # Verify calculate_order_fees was called with correct items and org_settings
        mock_fee_calc.calculate_order_fees.assert_called_once()
        call_args = mock_fee_calc.calculate_order_fees.call_args
        order_items = call_args[0][0]
        called_org_settings = call_args[0][1]

        assert len(order_items) == 2
        assert order_items[0].ticket_type_name == "General Admission"
        assert order_items[0].quantity == 2
        assert order_items[0].unit_price == 5000
        assert order_items[1].ticket_type_name == "VIP"
        assert order_items[1].quantity == 1
        assert order_items[1].unit_price == 10000
        assert called_org_settings == org_settings

    @patch(_ORDER_MODEL_PATCH)
    @patch(_FEE_CALC_PATCH)
    @patch(_PROVIDER_FACTORY_PATCH)
    @patch(_CRUD_PATCH)
    def test_no_platform_fee_when_no_connected_account(
        self, mock_crud, mock_provider_factory, mock_fee_calc, mock_order_model
    ):
        """When connected_acct_id is None (free ticket), platform_fee_amount is None in intent."""
        event = _make_event()
        free_ticket = _make_ticket_type(id="tt_free_001", price=0, name="Free Entry")

        mock_crud.event.get.return_value = event
        mock_crud.ticket_type.get.return_value = free_ticket
        mock_crud.ticket_type.is_available.return_value = True
        mock_crud.ticket_type.reserve_quantity.return_value = True

        mock_order = _make_order(total_amount=0, subtotal=0, platform_fee=0)
        mock_crud.order.create_order.return_value = mock_order
        mock_order_model.generate_order_number.return_value = "ORD-2026-FREE01"

        with patch("app.schemas.payment.Order.model_validate") as mock_validate:
            mock_validate.return_value = MagicMock()

            input_data = _make_checkout_input(
                items=[OrderItemCreate(ticket_type_id="tt_free_001", quantity=1)]
            )

            run_async(
                self.service.create_checkout_session(
                    input_data=input_data,
                    organization_id="org_123",
                )
            )

        # No payment intent created for free order
        mock_provider_factory.assert_not_called()
        # No fee calculation for free order
        mock_fee_calc.calculate_order_fees.assert_not_called()


class TestRefundWithConnect:
    """
    Verify that refunds work correctly for orders processed through
    Stripe Connect, including email notifications.
    """

    def setup_method(self):
        """Set up a PaymentService with a mocked DB session."""
        self.mock_db = MagicMock()
        self.service = PaymentService(self.mock_db)

    @patch("app.services.payment.payment_service.get_payment_provider")
    @patch(_CRUD_PATCH)
    def test_refund_email_triggered_on_successful_refund(
        self, mock_crud, mock_get_provider
    ):
        """Refund confirmation email is sent when refund succeeds immediately."""
        order = _make_order(
            status="completed",
            connected_account_id="acct_test123",
            guest_email="buyer@example.com",
            customer_name="John Doe",
        )
        payment = _make_payment(refundable_amount=5000)

        mock_crud.order.get_with_items.return_value = order
        mock_crud.payment.get_successful_payment.return_value = payment
        mock_crud.refund.create_refund.return_value = MagicMock(
            id="ref_abc123", status="pending"
        )

        # Provider returns successful refund
        mock_provider = MagicMock()
        mock_provider.create_refund = AsyncMock(
            return_value=RefundResult(
                refund_id="re_stripe_123",
                status=RefundStatusEnum.SUCCEEDED,
                amount=5000,
                currency="USD",
            )
        )
        mock_get_provider.return_value = mock_provider

        refund_input = InitiateRefundInput(
            order_id="ord_abc123def456",
            amount=5000,
            reason=RefundReason.requested_by_customer,
            reason_details="Customer requested refund",
        )

        # Patch the email sending functions used in _send_refund_email
        with patch(
            "app.services.payment.payment_service.crud"
        ) as inner_crud:
            # The _send_refund_email method calls crud.event.get internally
            inner_crud.order.get_with_items.return_value = order
            inner_crud.payment.get_successful_payment.return_value = payment
            inner_crud.refund.create_refund.return_value = MagicMock(
                id="ref_abc123", status="pending"
            )
            inner_crud.event.get.return_value = _make_event()

            with patch(
                "app.utils.kafka_helpers.publish_refund_confirmation_email",
                return_value=True,
            ) as mock_kafka_email:
                run_async(
                    self.service.initiate_refund(
                        input_data=refund_input,
                        initiated_by_user_id="admin_user_001",
                    )
                )

                # Verify refund email was attempted via Kafka
                mock_kafka_email.assert_called_once_with(
                    to_email="buyer@example.com",
                    buyer_name="John Doe",
                    event_name="Test Conference 2026",
                    order_number="ORD-2026-A1B2C3",
                    refund_amount_cents=5000,
                    currency="USD",
                )

    @patch("app.services.payment.payment_service.get_payment_provider")
    @patch(_CRUD_PATCH)
    def test_refund_handles_order_with_connected_account(
        self, mock_crud, mock_get_provider
    ):
        """Refund succeeds for orders that were processed via a connected account."""
        order = _make_order(
            status="completed",
            connected_account_id="acct_organizer_456",
            platform_fee=275,
            fee_absorption="absorb",
            fee_breakdown_json={
                "platform_fee_total": 275,
                "fee_percent_used": 4.0,
                "fee_fixed_used": 75,
                "absorption_model": "absorb",
                "per_item_fees": [
                    {
                        "ticket_type_name": "GA",
                        "quantity": 1,
                        "unit_price": 5000,
                        "fee_per_ticket": 275,
                        "fee_subtotal": 275,
                    }
                ],
            },
        )
        payment = _make_payment(
            refundable_amount=5000,
            provider_intent_id="pi_connect_123",
            provider_payment_id="pi_connect_123",
        )

        mock_crud.order.get_with_items.return_value = order
        mock_crud.payment.get_successful_payment.return_value = payment
        mock_crud.refund.create_refund.return_value = MagicMock(
            id="ref_connect_001", status="pending"
        )
        mock_crud.event.get.return_value = _make_event()

        # Provider returns successful refund
        mock_provider = MagicMock()
        mock_provider.create_refund = AsyncMock(
            return_value=RefundResult(
                refund_id="re_connect_456",
                status=RefundStatusEnum.SUCCEEDED,
                amount=5000,
                currency="USD",
            )
        )
        mock_get_provider.return_value = mock_provider

        refund_input = InitiateRefundInput(
            order_id="ord_abc123def456",
            amount=5000,
            reason=RefundReason.event_cancelled,
            reason_details="Event was cancelled",
        )

        with patch(
            "app.utils.kafka_helpers.publish_refund_confirmation_email",
            return_value=True,
        ):
            result = run_async(
                self.service.initiate_refund(
                    input_data=refund_input,
                    initiated_by_user_id="admin_user_001",
                )
            )

        # Verify refund was created via provider
        mock_provider.create_refund.assert_called_once()
        refund_params = mock_provider.create_refund.call_args[0][0]
        assert refund_params.payment_id == "pi_connect_123"
        assert refund_params.amount == 5000

        # Verify refund status was updated
        mock_crud.refund.update_status.assert_called_once_with(
            self.mock_db,
            refund_id="ref_connect_001",
            status=RefundStatus.succeeded,
            provider_refund_id="re_connect_456",
        )

        # Verify payment refunded amount was updated
        mock_crud.payment.add_refunded_amount.assert_called_once_with(
            self.mock_db, payment_id=payment.id, amount=5000
        )

    @patch("app.services.payment.payment_service.get_payment_provider")
    @patch(_CRUD_PATCH)
    def test_refund_updates_order_status_to_refunded_for_full_refund(
        self, mock_crud, mock_get_provider
    ):
        """Full refund sets order status to 'refunded'."""
        order = _make_order(
            status="completed",
            connected_account_id="acct_test123",
            total_amount=5000,
        )
        payment = _make_payment(
            amount=5000, amount_refunded=0, refundable_amount=5000
        )

        mock_crud.order.get_with_items.return_value = order
        mock_crud.payment.get_successful_payment.return_value = payment
        mock_crud.refund.create_refund.return_value = MagicMock(
            id="ref_full_001", status="pending"
        )
        mock_crud.event.get.return_value = _make_event()

        mock_provider = MagicMock()
        mock_provider.create_refund = AsyncMock(
            return_value=RefundResult(
                refund_id="re_full_001",
                status=RefundStatusEnum.SUCCEEDED,
                amount=5000,
                currency="USD",
            )
        )
        mock_get_provider.return_value = mock_provider

        refund_input = InitiateRefundInput(
            order_id="ord_abc123def456",
            amount=5000,
            reason=RefundReason.requested_by_customer,
        )

        with patch(
            "app.utils.kafka_helpers.publish_refund_confirmation_email",
            return_value=True,
        ):
            run_async(
                self.service.initiate_refund(
                    input_data=refund_input,
                    initiated_by_user_id="admin_user_001",
                )
            )

        # Full refund: payment.amount_refunded (0) + refund_amount (5000) >= payment.amount (5000)
        assert order.status == "refunded"
        self.mock_db.add.assert_called_with(order)
        self.mock_db.commit.assert_called()

    @patch("app.services.payment.payment_service.get_payment_provider")
    @patch(_CRUD_PATCH)
    def test_refund_updates_order_status_to_partially_refunded(
        self, mock_crud, mock_get_provider
    ):
        """Partial refund sets order status to 'partially_refunded'."""
        order = _make_order(
            status="completed",
            connected_account_id="acct_test123",
            total_amount=5000,
        )
        payment = _make_payment(
            amount=5000, amount_refunded=0, refundable_amount=5000
        )

        mock_crud.order.get_with_items.return_value = order
        mock_crud.payment.get_successful_payment.return_value = payment
        mock_crud.refund.create_refund.return_value = MagicMock(
            id="ref_partial_001", status="pending"
        )
        mock_crud.event.get.return_value = _make_event()

        mock_provider = MagicMock()
        mock_provider.create_refund = AsyncMock(
            return_value=RefundResult(
                refund_id="re_partial_001",
                status=RefundStatusEnum.SUCCEEDED,
                amount=2500,
                currency="USD",
            )
        )
        mock_get_provider.return_value = mock_provider

        refund_input = InitiateRefundInput(
            order_id="ord_abc123def456",
            amount=2500,  # Partial refund
            reason=RefundReason.requested_by_customer,
        )

        with patch(
            "app.utils.kafka_helpers.publish_refund_confirmation_email",
            return_value=True,
        ):
            run_async(
                self.service.initiate_refund(
                    input_data=refund_input,
                    initiated_by_user_id="admin_user_001",
                )
            )

        # Partial refund: payment.amount_refunded (0) + refund_amount (2500) < payment.amount (5000)
        assert order.status == "partially_refunded"

    @patch("app.services.payment.payment_service.get_payment_provider")
    @patch(_CRUD_PATCH)
    def test_refund_no_email_when_refund_status_pending(
        self, mock_crud, mock_get_provider
    ):
        """No refund email is sent when refund status is 'pending' (not immediately succeeded)."""
        order = _make_order(
            status="completed",
            connected_account_id="acct_test123",
            guest_email="buyer@example.com",
        )
        payment = _make_payment(refundable_amount=5000)

        mock_crud.order.get_with_items.return_value = order
        mock_crud.payment.get_successful_payment.return_value = payment
        mock_crud.refund.create_refund.return_value = MagicMock(
            id="ref_pending_001", status="pending"
        )
        mock_crud.event.get.return_value = _make_event()

        # Provider returns pending (not succeeded) refund
        mock_provider = MagicMock()
        mock_provider.create_refund = AsyncMock(
            return_value=RefundResult(
                refund_id="re_pending_001",
                status=RefundStatusEnum.PENDING,
                amount=5000,
                currency="USD",
            )
        )
        mock_get_provider.return_value = mock_provider

        refund_input = InitiateRefundInput(
            order_id="ord_abc123def456",
            amount=5000,
            reason=RefundReason.requested_by_customer,
        )

        with patch(
            "app.utils.kafka_helpers.publish_refund_confirmation_email",
            return_value=True,
        ) as mock_kafka_email:
            run_async(
                self.service.initiate_refund(
                    input_data=refund_input,
                    initiated_by_user_id="admin_user_001",
                )
            )

            # Email should NOT be sent for pending refunds
            mock_kafka_email.assert_not_called()
