"""
Tests for the refund flow with Stripe Connect.

Verifies that:
- PaymentService.initiate_refund correctly orchestrates refund creation,
  provider calls, order status updates, audit logging, and email sending
- _send_refund_email uses Kafka-first with direct fallback, handles missing
  emails and exceptions gracefully
- Webhook handlers (_handle_charge_refunded, _handle_refund_succeeded,
  _handle_refund_failed) update payment/order/refund records correctly
- Connect-specific refund fields (refund_application_fee) are wired through
  to the Stripe provider

All external dependencies (crud, providers, email, user service) are mocked.
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call
from datetime import datetime, timezone

from app.services.payment.payment_service import PaymentService
from app.services.payment.provider_interface import (
    CreateRefundParams,
    RefundResult,
    RefundStatusEnum,
    RefundReason as ProviderRefundReason,
)
from app.services.payment.providers.stripe_provider import PaymentError
from app.schemas.payment import (
    InitiateRefundInput,
    RefundReason,
    RefundStatus,
)


def run_async(coro):
    """Helper to run async coroutines in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


# --------------------------------------------------------------------------- #
# Factory helpers for mock objects
# --------------------------------------------------------------------------- #

def _make_order(**overrides):
    """Create a mock Order object with sensible defaults."""
    defaults = {
        "id": "ord_abc123",
        "organization_id": "org_123",
        "event_id": "evt_456",
        "status": "completed",
        "currency": "USD",
        "total_amount": 5000,
        "subtotal": 5000,
        "platform_fee": 275,
        "payment_intent_id": "pi_test_intent",
        "payment_provider": "stripe",
        "order_number": "ORD-20260215-0001",
        "guest_email": "buyer@example.com",
        "customer_name": "Jane Doe",
        "user_id": None,
        "promo_code_id": None,
        "fee_absorption": "absorb",
        "items": [],
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    for key, val in defaults.items():
        setattr(mock, key, val)
    return mock


def _make_payment(**overrides):
    """Create a mock Payment object with sensible defaults."""
    defaults = {
        "id": "pay_789",
        "order_id": "ord_abc123",
        "organization_id": "org_123",
        "provider_code": "stripe",
        "provider_payment_id": "pi_test_intent",
        "provider_intent_id": "pi_test_intent",
        "status": "succeeded",
        "currency": "USD",
        "amount": 5000,
        "amount_refunded": 0,
        "refundable_amount": 5000,
        "net_amount": 5000,
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    for key, val in defaults.items():
        setattr(mock, key, val)
    return mock


def _make_refund(**overrides):
    """Create a mock Refund object with sensible defaults."""
    defaults = {
        "id": "ref_001",
        "payment_id": "pay_789",
        "order_id": "ord_abc123",
        "organization_id": "org_123",
        "provider_code": "stripe",
        "amount": 5000,
        "currency": "USD",
        "status": "pending",
        "reason": "requested_by_customer",
        "reason_details": None,
        "provider_refund_id": None,
        "initiated_by_user_id": "user_admin",
        "idempotency_key": "refund_ord_abc123_aabbccdd",
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    for key, val in defaults.items():
        setattr(mock, key, val)
    return mock


def _make_event(**overrides):
    """Create a mock Event object."""
    defaults = {
        "id": "evt_456",
        "name": "Test Concert",
        "owner_id": "user_owner",
        "start_date": datetime(2026, 6, 15, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    for key, val in defaults.items():
        setattr(mock, key, val)
    return mock


def _make_webhook_event(event_type, data):
    """Create a mock webhook event object."""
    mock = MagicMock()
    mock.event_type = event_type
    mock.event_id = "evt_webhook_123"
    mock.data = data
    mock.created_at = datetime.now(timezone.utc)
    mock.raw_payload = {}
    return mock


def _succeeded_refund_result(**overrides):
    """Create a RefundResult indicating success."""
    defaults = {
        "refund_id": "re_stripe_001",
        "status": RefundStatusEnum.SUCCEEDED,
        "amount": 5000,
        "currency": "USD",
    }
    defaults.update(overrides)
    return RefundResult(**defaults)


def _pending_refund_result(**overrides):
    """Create a RefundResult indicating pending."""
    defaults = {
        "refund_id": "re_stripe_001",
        "status": RefundStatusEnum.PENDING,
        "amount": 5000,
        "currency": "USD",
    }
    defaults.update(overrides)
    return RefundResult(**defaults)


# =========================================================================== #
#  1. PaymentService.initiate_refund
# =========================================================================== #

class TestInitiateRefund:
    """Tests for PaymentService.initiate_refund."""

    def setup_method(self):
        self.mock_db = MagicMock()
        self.service = PaymentService(db=self.mock_db)

    # -- Full refund succeeds ------------------------------------------------ #

    @patch("app.services.payment.payment_service.get_payment_provider")
    @patch("app.services.payment.payment_service.crud")
    def test_full_refund_succeeds_and_triggers_email(self, mock_crud, mock_get_provider):
        """Full refund processes correctly, updates order to 'refunded', and sends email."""
        order = _make_order()
        payment = _make_payment()
        refund = _make_refund()

        mock_crud.order.get_with_items.return_value = order
        mock_crud.payment.get_successful_payment.return_value = payment
        mock_crud.refund.create_refund.return_value = refund

        provider = AsyncMock()
        provider.create_refund.return_value = _succeeded_refund_result()
        mock_get_provider.return_value = provider

        input_data = InitiateRefundInput(
            order_id="ord_abc123",
            reason=RefundReason.requested_by_customer,
        )

        with patch.object(self.service, "_send_refund_email", new_callable=AsyncMock) as mock_email:
            result = run_async(
                self.service.initiate_refund(
                    input_data=input_data,
                    initiated_by_user_id="user_admin",
                    request_id="req_001",
                )
            )

        # Refund record was created
        mock_crud.refund.create_refund.assert_called_once()

        # Provider was called
        provider.create_refund.assert_called_once()

        # Refund status updated to succeeded
        mock_crud.refund.update_status.assert_called_once()
        status_call = mock_crud.refund.update_status.call_args
        assert status_call.kwargs.get("status") == RefundStatus.succeeded or \
               status_call[1].get("status") == RefundStatus.succeeded

        # Payment refunded amount was updated
        mock_crud.payment.add_refunded_amount.assert_called_once_with(
            self.mock_db, payment_id="pay_789", amount=5000
        )

        # Order status set to "refunded" (full refund: 0 + 5000 >= 5000)
        assert order.status == "refunded"
        self.mock_db.add.assert_called_with(order)
        self.mock_db.commit.assert_called()

        # Refund email sent
        mock_email.assert_awaited_once_with(order, 5000, "USD")

    # -- Partial refund ------------------------------------------------------ #

    @patch("app.services.payment.payment_service.get_payment_provider")
    @patch("app.services.payment.payment_service.crud")
    def test_partial_refund_sets_partially_refunded(self, mock_crud, mock_get_provider):
        """Partial refund updates order status to 'partially_refunded'."""
        order = _make_order()
        payment = _make_payment()
        refund = _make_refund(amount=2000)

        mock_crud.order.get_with_items.return_value = order
        mock_crud.payment.get_successful_payment.return_value = payment
        mock_crud.refund.create_refund.return_value = refund

        provider = AsyncMock()
        provider.create_refund.return_value = _succeeded_refund_result(amount=2000)
        mock_get_provider.return_value = provider

        input_data = InitiateRefundInput(
            order_id="ord_abc123",
            amount=2000,
            reason=RefundReason.requested_by_customer,
        )

        with patch.object(self.service, "_send_refund_email", new_callable=AsyncMock):
            run_async(
                self.service.initiate_refund(
                    input_data=input_data,
                    initiated_by_user_id="user_admin",
                )
            )

        # 0 (amount_refunded) + 2000 < 5000 (payment.amount) => partially_refunded
        assert order.status == "partially_refunded"

    # -- Refund amount exceeds refundable ------------------------------------ #

    @patch("app.services.payment.payment_service.crud")
    def test_refund_exceeds_refundable_raises(self, mock_crud):
        """Refund amount exceeding refundable amount raises ValueError."""
        order = _make_order()
        payment = _make_payment(refundable_amount=3000)

        mock_crud.order.get_with_items.return_value = order
        mock_crud.payment.get_successful_payment.return_value = payment

        input_data = InitiateRefundInput(
            order_id="ord_abc123",
            amount=4000,
            reason=RefundReason.requested_by_customer,
        )

        with pytest.raises(ValueError, match="exceeds refundable amount"):
            run_async(
                self.service.initiate_refund(
                    input_data=input_data,
                    initiated_by_user_id="user_admin",
                )
            )

    # -- No successful payment ----------------------------------------------- #

    @patch("app.services.payment.payment_service.crud")
    def test_no_successful_payment_raises(self, mock_crud):
        """No successful payment found raises ValueError."""
        order = _make_order()

        mock_crud.order.get_with_items.return_value = order
        mock_crud.payment.get_successful_payment.return_value = None

        input_data = InitiateRefundInput(
            order_id="ord_abc123",
            reason=RefundReason.requested_by_customer,
        )

        with pytest.raises(ValueError, match="No successful payment"):
            run_async(
                self.service.initiate_refund(
                    input_data=input_data,
                    initiated_by_user_id="user_admin",
                )
            )

    # -- Order not in refundable status -------------------------------------- #

    @patch("app.services.payment.payment_service.crud")
    def test_order_wrong_status_raises(self, mock_crud):
        """Order not in completed/partially_refunded status raises ValueError."""
        order = _make_order(status="pending")
        mock_crud.order.get_with_items.return_value = order

        input_data = InitiateRefundInput(
            order_id="ord_abc123",
            reason=RefundReason.requested_by_customer,
        )

        with pytest.raises(ValueError, match="cannot be refunded"):
            run_async(
                self.service.initiate_refund(
                    input_data=input_data,
                    initiated_by_user_id="user_admin",
                )
            )

    @patch("app.services.payment.payment_service.crud")
    def test_order_cancelled_status_raises(self, mock_crud):
        """Order in cancelled status raises ValueError."""
        order = _make_order(status="cancelled")
        mock_crud.order.get_with_items.return_value = order

        input_data = InitiateRefundInput(
            order_id="ord_abc123",
            reason=RefundReason.requested_by_customer,
        )

        with pytest.raises(ValueError, match="cannot be refunded"):
            run_async(
                self.service.initiate_refund(
                    input_data=input_data,
                    initiated_by_user_id="user_admin",
                )
            )

    # -- Order already partially_refunded can be refunded again -------------- #

    @patch("app.services.payment.payment_service.get_payment_provider")
    @patch("app.services.payment.payment_service.crud")
    def test_partially_refunded_order_can_be_refunded_again(self, mock_crud, mock_get_provider):
        """Order in partially_refunded status can accept another refund."""
        order = _make_order(status="partially_refunded")
        payment = _make_payment(amount_refunded=2000, refundable_amount=3000)
        refund = _make_refund(amount=3000)

        mock_crud.order.get_with_items.return_value = order
        mock_crud.payment.get_successful_payment.return_value = payment
        mock_crud.refund.create_refund.return_value = refund

        provider = AsyncMock()
        provider.create_refund.return_value = _succeeded_refund_result(amount=3000)
        mock_get_provider.return_value = provider

        input_data = InitiateRefundInput(
            order_id="ord_abc123",
            amount=3000,
            reason=RefundReason.requested_by_customer,
        )

        with patch.object(self.service, "_send_refund_email", new_callable=AsyncMock):
            run_async(
                self.service.initiate_refund(
                    input_data=input_data,
                    initiated_by_user_id="user_admin",
                )
            )

        # 2000 + 3000 = 5000 >= 5000 => fully refunded
        assert order.status == "refunded"

    # -- Provider failure marks refund as failed ----------------------------- #

    @patch("app.services.payment.payment_service.get_payment_provider")
    @patch("app.services.payment.payment_service.crud")
    def test_provider_failure_marks_refund_failed(self, mock_crud, mock_get_provider):
        """Provider refund failure marks refund as failed and raises ValueError."""
        order = _make_order()
        payment = _make_payment()
        refund = _make_refund()

        mock_crud.order.get_with_items.return_value = order
        mock_crud.payment.get_successful_payment.return_value = payment
        mock_crud.refund.create_refund.return_value = refund

        provider = AsyncMock()
        provider.create_refund.side_effect = PaymentError(
            code="INVALID_REFUND",
            message="Charge already fully refunded",
            retryable=False,
        )
        mock_get_provider.return_value = provider

        input_data = InitiateRefundInput(
            order_id="ord_abc123",
            reason=RefundReason.requested_by_customer,
        )

        with pytest.raises(ValueError, match="Refund failed"):
            run_async(
                self.service.initiate_refund(
                    input_data=input_data,
                    initiated_by_user_id="user_admin",
                )
            )

        # Refund status updated to failed
        mock_crud.refund.update_status.assert_called_once()
        status_call = mock_crud.refund.update_status.call_args
        assert status_call.kwargs.get("status") == RefundStatus.failed or \
               status_call[1].get("status") == RefundStatus.failed
        assert status_call.kwargs.get("failure_code") == "INVALID_REFUND" or \
               status_call[1].get("failure_code") == "INVALID_REFUND"

    # -- Audit log entries created ------------------------------------------- #

    @patch("app.services.payment.payment_service.get_payment_provider")
    @patch("app.services.payment.payment_service.crud")
    def test_refund_creates_audit_log_entries(self, mock_crud, mock_get_provider):
        """Refund creates audit log entries for initiation and success."""
        order = _make_order()
        payment = _make_payment()
        refund = _make_refund()

        mock_crud.order.get_with_items.return_value = order
        mock_crud.payment.get_successful_payment.return_value = payment
        mock_crud.refund.create_refund.return_value = refund

        provider = AsyncMock()
        provider.create_refund.return_value = _succeeded_refund_result()
        mock_get_provider.return_value = provider

        input_data = InitiateRefundInput(
            order_id="ord_abc123",
            reason=RefundReason.requested_by_customer,
        )

        with patch.object(self.service, "_send_refund_email", new_callable=AsyncMock):
            run_async(
                self.service.initiate_refund(
                    input_data=input_data,
                    initiated_by_user_id="user_admin",
                    request_id="req_001",
                )
            )

        # Should have at least 2 audit log calls: initiated + succeeded
        audit_calls = mock_crud.audit_log.log_action.call_args_list
        assert len(audit_calls) >= 2

        # First call: refund.initiated
        first_call_kwargs = audit_calls[0].kwargs
        assert first_call_kwargs["action"] == "refund.initiated"
        assert first_call_kwargs["actor_type"] == "admin"
        assert first_call_kwargs["actor_id"] == "user_admin"
        assert first_call_kwargs["entity_type"] == "refund"

        # Second call: refund.succeeded
        second_call_kwargs = audit_calls[1].kwargs
        assert second_call_kwargs["action"] == "refund.succeeded"
        assert second_call_kwargs["actor_type"] == "system"

    # -- Order not found ----------------------------------------------------- #

    @patch("app.services.payment.payment_service.crud")
    def test_order_not_found_raises(self, mock_crud):
        """Order not found raises ValueError."""
        mock_crud.order.get_with_items.return_value = None

        input_data = InitiateRefundInput(
            order_id="ord_nonexistent",
            reason=RefundReason.requested_by_customer,
        )

        with pytest.raises(ValueError, match="Order not found"):
            run_async(
                self.service.initiate_refund(
                    input_data=input_data,
                    initiated_by_user_id="user_admin",
                )
            )

    # -- Pending provider result does not send email ------------------------- #

    @patch("app.services.payment.payment_service.get_payment_provider")
    @patch("app.services.payment.payment_service.crud")
    def test_pending_refund_does_not_send_email(self, mock_crud, mock_get_provider):
        """When provider returns 'pending' status, email is NOT sent."""
        order = _make_order()
        payment = _make_payment()
        refund = _make_refund()

        mock_crud.order.get_with_items.return_value = order
        mock_crud.payment.get_successful_payment.return_value = payment
        mock_crud.refund.create_refund.return_value = refund

        provider = AsyncMock()
        provider.create_refund.return_value = _pending_refund_result()
        mock_get_provider.return_value = provider

        input_data = InitiateRefundInput(
            order_id="ord_abc123",
            reason=RefundReason.requested_by_customer,
        )

        with patch.object(self.service, "_send_refund_email", new_callable=AsyncMock) as mock_email:
            run_async(
                self.service.initiate_refund(
                    input_data=input_data,
                    initiated_by_user_id="user_admin",
                )
            )

        mock_email.assert_not_awaited()

    # -- Zero refundable amount ---------------------------------------------- #

    @patch("app.services.payment.payment_service.crud")
    def test_zero_refundable_amount_raises(self, mock_crud):
        """When refundable_amount is 0, raises ValueError."""
        order = _make_order()
        payment = _make_payment(refundable_amount=0, amount_refunded=5000)

        mock_crud.order.get_with_items.return_value = order
        mock_crud.payment.get_successful_payment.return_value = payment

        input_data = InitiateRefundInput(
            order_id="ord_abc123",
            reason=RefundReason.requested_by_customer,
        )

        with pytest.raises(ValueError, match="No refundable amount"):
            run_async(
                self.service.initiate_refund(
                    input_data=input_data,
                    initiated_by_user_id="user_admin",
                )
            )


# =========================================================================== #
#  2. _send_refund_email
# =========================================================================== #

class TestSendRefundEmail:
    """Tests for PaymentService._send_refund_email.

    Note: _send_refund_email uses lazy (inline) imports, so we patch at
    the source modules rather than at payment_service module level.
    """

    def setup_method(self):
        self.mock_db = MagicMock()
        self.service = PaymentService(db=self.mock_db)

    @patch("app.utils.kafka_helpers.publish_refund_confirmation_email", return_value=True)
    @patch("app.core.email.send_refund_confirmation_email")
    @patch("app.services.payment.payment_service.crud")
    def test_sends_via_kafka_first(self, mock_crud, mock_direct, mock_kafka):
        """_send_refund_email sends via Kafka first, does not call direct if Kafka succeeds."""
        order = _make_order(guest_email="buyer@test.com", customer_name="Test User")
        event = _make_event()
        mock_crud.event.get.return_value = event

        run_async(self.service._send_refund_email(order, 5000, "USD"))

        mock_kafka.assert_called_once_with(
            to_email="buyer@test.com",
            buyer_name="Test User",
            event_name="Test Concert",
            order_number="ORD-20260215-0001",
            refund_amount_cents=5000,
            currency="USD",
        )
        mock_direct.assert_not_called()

    @patch("app.core.email.send_refund_confirmation_email")
    @patch("app.utils.kafka_helpers.publish_refund_confirmation_email", return_value=False)
    @patch("app.services.payment.payment_service.crud")
    def test_falls_back_to_direct_when_kafka_fails(self, mock_crud, mock_kafka, mock_direct):
        """_send_refund_email falls back to direct send when Kafka returns False."""
        order = _make_order(guest_email="buyer@test.com", customer_name="Test User")
        event = _make_event()
        mock_crud.event.get.return_value = event

        run_async(self.service._send_refund_email(order, 5000, "USD"))

        mock_kafka.assert_called_once()
        mock_direct.assert_called_once_with(
            to_email="buyer@test.com",
            buyer_name="Test User",
            event_name="Test Concert",
            order_number="ORD-20260215-0001",
            refund_amount_cents=5000,
            currency="USD",
        )

    @patch("app.utils.kafka_helpers.publish_refund_confirmation_email")
    @patch("app.services.payment.payment_service.crud")
    def test_handles_missing_buyer_email_gracefully(self, mock_crud, mock_kafka):
        """Returns early without sending if buyer email is empty and no user_id."""
        order = _make_order(guest_email="", customer_name="No Email", user_id=None)
        event = _make_event()
        mock_crud.event.get.return_value = event

        run_async(self.service._send_refund_email(order, 5000, "USD"))

        mock_kafka.assert_not_called()

    @patch("app.utils.kafka_helpers.publish_refund_confirmation_email", return_value=True)
    @patch("app.utils.user_service.get_user_info_async", new_callable=AsyncMock)
    @patch("app.services.payment.payment_service.crud")
    def test_fetches_email_from_user_service_when_guest_email_empty(
        self, mock_crud, mock_user_info, mock_kafka
    ):
        """When guest_email is empty but user_id is set, fetches email from user service."""
        order = _make_order(guest_email="", user_id="user_123")
        event = _make_event()
        mock_crud.event.get.return_value = event
        mock_user_info.return_value = {"email": "fetched@test.com", "name": "Fetched User"}

        run_async(self.service._send_refund_email(order, 5000, "USD"))

        mock_kafka.assert_called_once()
        call_kwargs = mock_kafka.call_args.kwargs
        assert call_kwargs["to_email"] == "fetched@test.com"
        assert call_kwargs["buyer_name"] == "Fetched User"

    @patch("app.services.payment.payment_service.crud")
    def test_handles_exception_without_propagating(self, mock_crud):
        """Exceptions inside _send_refund_email are caught and do not propagate."""
        order = _make_order(guest_email="buyer@test.com")
        mock_crud.event.get.side_effect = Exception("DB connection failed")

        # Should not raise
        run_async(self.service._send_refund_email(order, 5000, "USD"))

    @patch("app.utils.kafka_helpers.publish_refund_confirmation_email")
    @patch("app.utils.user_service.get_user_info_async", new_callable=AsyncMock)
    @patch("app.services.payment.payment_service.crud")
    def test_user_service_returns_none_and_no_guest_email(self, mock_crud, mock_user_info, mock_kafka):
        """When user service returns None and no guest_email, skips email."""
        order = _make_order(guest_email="", user_id="user_123")
        event = _make_event()
        mock_crud.event.get.return_value = event
        mock_user_info.return_value = None

        run_async(self.service._send_refund_email(order, 5000, "USD"))

        mock_kafka.assert_not_called()


# =========================================================================== #
#  3. Webhook Refund Handlers
# =========================================================================== #

class TestWebhookChargeRefunded:
    """Tests for _handle_charge_refunded webhook handler."""

    def setup_method(self):
        self.mock_db = MagicMock()

    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_updates_payment_amount_refunded(self, mock_crud):
        """_handle_charge_refunded updates payment.amount_refunded."""
        from app.api.v1.endpoints.webhooks import _handle_charge_refunded

        payment = _make_payment(amount=5000, amount_refunded=0)
        order = _make_order()

        mock_crud.payment.get_by_provider_intent_id.return_value = payment
        mock_crud.order.get.return_value = order

        event = _make_webhook_event(
            event_type="charge.refunded",
            data={"paymentIntentId": "pi_test_intent", "amount": 5000},
        )

        result = run_async(_handle_charge_refunded(self.mock_db, event))

        mock_crud.payment.add_refunded_amount.assert_called_once_with(
            self.mock_db, payment_id="pay_789", amount=5000
        )
        assert result["payment_id"] == "pay_789"
        assert result["order_id"] == "ord_abc123"

    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_sets_order_refunded_when_fully_refunded(self, mock_crud):
        """Sets order to 'refunded' when amount_refunded >= amount."""
        from app.api.v1.endpoints.webhooks import _handle_charge_refunded

        payment = _make_payment(amount=5000, amount_refunded=5000)
        order = _make_order()

        mock_crud.payment.get_by_provider_intent_id.return_value = payment
        mock_crud.order.get.return_value = order

        event = _make_webhook_event(
            event_type="charge.refunded",
            data={"paymentIntentId": "pi_test_intent", "amount": 5000},
        )

        run_async(_handle_charge_refunded(self.mock_db, event))

        assert order.status == "refunded"
        self.mock_db.add.assert_called_with(order)
        self.mock_db.commit.assert_called()

    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_sets_order_partially_refunded_for_partial(self, mock_crud):
        """Sets order to 'partially_refunded' when amount_refunded < amount."""
        from app.api.v1.endpoints.webhooks import _handle_charge_refunded

        payment = _make_payment(amount=5000, amount_refunded=2000)
        order = _make_order()

        mock_crud.payment.get_by_provider_intent_id.return_value = payment
        mock_crud.order.get.return_value = order

        event = _make_webhook_event(
            event_type="charge.refunded",
            data={"paymentIntentId": "pi_test_intent", "amount": 2000},
        )

        run_async(_handle_charge_refunded(self.mock_db, event))

        assert order.status == "partially_refunded"

    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_no_payment_found_returns_empty(self, mock_crud):
        """Returns empty dict when no payment found for intent ID."""
        from app.api.v1.endpoints.webhooks import _handle_charge_refunded

        mock_crud.payment.get_by_provider_intent_id.return_value = None

        event = _make_webhook_event(
            event_type="charge.refunded",
            data={"paymentIntentId": "pi_unknown"},
        )

        result = run_async(_handle_charge_refunded(self.mock_db, event))
        assert result == {}

    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_no_intent_id_returns_empty(self, mock_crud):
        """Returns empty dict when event has no paymentIntentId."""
        from app.api.v1.endpoints.webhooks import _handle_charge_refunded

        event = _make_webhook_event(
            event_type="charge.refunded",
            data={},
        )

        result = run_async(_handle_charge_refunded(self.mock_db, event))
        assert result == {}


class TestWebhookRefundSucceeded:
    """Tests for _handle_refund_succeeded webhook handler."""

    def setup_method(self):
        self.mock_db = MagicMock()

    @patch("app.api.v1.endpoints.webhooks._send_refund_confirmation_email", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_updates_refund_status_and_sends_email(self, mock_crud, mock_send_email):
        """_handle_refund_succeeded updates status to succeeded and sends email."""
        from app.api.v1.endpoints.webhooks import _handle_refund_succeeded

        refund = _make_refund(id="ref_001", order_id="ord_abc123")
        mock_crud.refund.get_by_provider_refund_id.return_value = refund

        event = _make_webhook_event(
            event_type="refund.succeeded",
            data={"refundId": "re_stripe_001"},
        )

        result = run_async(_handle_refund_succeeded(self.mock_db, event))

        # Refund status updated
        mock_crud.refund.update_status.assert_called_once_with(
            self.mock_db,
            refund_id="ref_001",
            status=RefundStatus.succeeded,
        )

        # Email sent
        mock_send_email.assert_awaited_once_with(self.mock_db, refund)

        assert result["refund_id"] == "ref_001"
        assert result["order_id"] == "ord_abc123"

    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_no_refund_found_returns_empty(self, mock_crud):
        """Returns empty dict when no refund record matches provider refund ID."""
        from app.api.v1.endpoints.webhooks import _handle_refund_succeeded

        mock_crud.refund.get_by_provider_refund_id.return_value = None

        event = _make_webhook_event(
            event_type="refund.succeeded",
            data={"refundId": "re_unknown"},
        )

        result = run_async(_handle_refund_succeeded(self.mock_db, event))
        assert result == {}

    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_no_refund_id_returns_empty(self, mock_crud):
        """Returns empty dict when event has no refundId."""
        from app.api.v1.endpoints.webhooks import _handle_refund_succeeded

        event = _make_webhook_event(
            event_type="refund.succeeded",
            data={},
        )

        result = run_async(_handle_refund_succeeded(self.mock_db, event))
        assert result == {}


class TestWebhookRefundFailed:
    """Tests for _handle_refund_failed webhook handler."""

    def setup_method(self):
        self.mock_db = MagicMock()

    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_marks_refund_failed_with_error_details(self, mock_crud):
        """_handle_refund_failed marks refund as failed with failure code and message."""
        from app.api.v1.endpoints.webhooks import _handle_refund_failed

        refund = _make_refund(id="ref_002", order_id="ord_abc123")
        mock_crud.refund.get_by_provider_refund_id.return_value = refund

        event = _make_webhook_event(
            event_type="refund.failed",
            data={
                "refundId": "re_stripe_002",
                "failureCode": "insufficient_funds",
                "failureMessage": "The connected account has insufficient funds.",
            },
        )

        result = run_async(_handle_refund_failed(self.mock_db, event))

        mock_crud.refund.update_status.assert_called_once_with(
            self.mock_db,
            refund_id="ref_002",
            status=RefundStatus.failed,
            failure_code="insufficient_funds",
            failure_message="The connected account has insufficient funds.",
        )

        assert result["refund_id"] == "ref_002"
        assert result["order_id"] == "ord_abc123"

    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_no_refund_found_returns_empty(self, mock_crud):
        """Returns empty dict when no refund record found."""
        from app.api.v1.endpoints.webhooks import _handle_refund_failed

        mock_crud.refund.get_by_provider_refund_id.return_value = None

        event = _make_webhook_event(
            event_type="refund.failed",
            data={"refundId": "re_unknown"},
        )

        result = run_async(_handle_refund_failed(self.mock_db, event))
        assert result == {}

    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_no_failure_details_passes_none(self, mock_crud):
        """When event has no failureCode/failureMessage, passes None."""
        from app.api.v1.endpoints.webhooks import _handle_refund_failed

        refund = _make_refund(id="ref_003")
        mock_crud.refund.get_by_provider_refund_id.return_value = refund

        event = _make_webhook_event(
            event_type="refund.failed",
            data={"refundId": "re_stripe_003"},
        )

        run_async(_handle_refund_failed(self.mock_db, event))

        call_kwargs = mock_crud.refund.update_status.call_args.kwargs
        assert call_kwargs["failure_code"] is None
        assert call_kwargs["failure_message"] is None


# =========================================================================== #
#  4. Connect-Specific Refund Behavior
# =========================================================================== #

class TestConnectRefundBehavior:
    """Tests for Stripe Connect specific refund parameters."""

    def test_create_refund_params_has_refund_application_fee_field(self):
        """CreateRefundParams dataclass accepts refund_application_fee."""
        params = CreateRefundParams(
            payment_id="pi_test",
            idempotency_key="idem_123",
            amount=5000,
            reason=ProviderRefundReason.REQUESTED_BY_CUSTOMER,
            refund_application_fee=True,
        )

        assert params.refund_application_fee is True

    def test_create_refund_params_refund_application_fee_defaults_none(self):
        """CreateRefundParams.refund_application_fee defaults to None."""
        params = CreateRefundParams(
            payment_id="pi_test",
            idempotency_key="idem_123",
        )

        assert params.refund_application_fee is None

    @patch("app.services.payment.providers.stripe_provider.stripe.Refund.create")
    def test_stripe_provider_passes_refund_application_fee(self, mock_refund_create):
        """Stripe provider passes refund_application_fee to Stripe API when set."""
        from app.services.payment.providers.stripe_provider import StripeProvider, StripeConfig

        mock_refund = MagicMock()
        mock_refund.id = "re_test_001"
        mock_refund.status = "succeeded"
        mock_refund.amount = 5000
        mock_refund.currency = "usd"
        mock_refund.charge = "ch_test"
        mock_refund.reason = "requested_by_customer"
        mock_refund_create.return_value = mock_refund

        config = StripeConfig(
            secret_key="sk_test_fake",
            publishable_key="pk_test_fake",
            webhook_secret="whsec_fake",
        )
        provider = StripeProvider(config)

        params = CreateRefundParams(
            payment_id="pi_test_intent",
            idempotency_key="idem_test_123",
            amount=5000,
            reason=ProviderRefundReason.REQUESTED_BY_CUSTOMER,
            refund_application_fee=True,
        )

        result = run_async(provider.create_refund(params))

        # Verify stripe.Refund.create was called with refund_application_fee=True
        mock_refund_create.assert_called_once()
        call_kwargs = mock_refund_create.call_args.kwargs
        assert call_kwargs["refund_application_fee"] is True
        assert call_kwargs["payment_intent"] == "pi_test_intent"
        assert call_kwargs["amount"] == 5000
        assert result.refund_id == "re_test_001"
        assert result.status == RefundStatusEnum.SUCCEEDED

    @patch("app.services.payment.providers.stripe_provider.stripe.Refund.create")
    def test_stripe_provider_omits_refund_application_fee_when_none(self, mock_refund_create):
        """Stripe provider does NOT pass refund_application_fee when it is None."""
        from app.services.payment.providers.stripe_provider import StripeProvider, StripeConfig

        mock_refund = MagicMock()
        mock_refund.id = "re_test_002"
        mock_refund.status = "succeeded"
        mock_refund.amount = 5000
        mock_refund.currency = "usd"
        mock_refund.charge = "ch_test"
        mock_refund.reason = "requested_by_customer"
        mock_refund_create.return_value = mock_refund

        config = StripeConfig(
            secret_key="sk_test_fake",
            publishable_key="pk_test_fake",
            webhook_secret="whsec_fake",
        )
        provider = StripeProvider(config)

        params = CreateRefundParams(
            payment_id="pi_test_intent",
            idempotency_key="idem_test_456",
            amount=5000,
            reason=ProviderRefundReason.REQUESTED_BY_CUSTOMER,
            refund_application_fee=None,
        )

        run_async(provider.create_refund(params))

        call_kwargs = mock_refund_create.call_args.kwargs
        assert "refund_application_fee" not in call_kwargs

    @patch("app.services.payment.providers.stripe_provider.stripe.Refund.create")
    def test_stripe_provider_passes_refund_application_fee_false(self, mock_refund_create):
        """Stripe provider passes refund_application_fee=False to keep platform fee."""
        from app.services.payment.providers.stripe_provider import StripeProvider, StripeConfig

        mock_refund = MagicMock()
        mock_refund.id = "re_test_003"
        mock_refund.status = "succeeded"
        mock_refund.amount = 2500
        mock_refund.currency = "usd"
        mock_refund.charge = "ch_test"
        mock_refund.reason = "requested_by_customer"
        mock_refund_create.return_value = mock_refund

        config = StripeConfig(
            secret_key="sk_test_fake",
            publishable_key="pk_test_fake",
            webhook_secret="whsec_fake",
        )
        provider = StripeProvider(config)

        params = CreateRefundParams(
            payment_id="pi_test_intent",
            idempotency_key="idem_test_789",
            amount=2500,
            reason=ProviderRefundReason.REQUESTED_BY_CUSTOMER,
            refund_application_fee=False,
        )

        result = run_async(provider.create_refund(params))

        call_kwargs = mock_refund_create.call_args.kwargs
        assert call_kwargs["refund_application_fee"] is False
        assert result.amount == 2500


# =========================================================================== #
#  5. Webhook _send_refund_confirmation_email (in webhooks.py)
# =========================================================================== #

class TestWebhookSendRefundConfirmationEmail:
    """Tests for the _send_refund_confirmation_email function in webhooks.py."""

    def setup_method(self):
        self.mock_db = MagicMock()

    @patch("app.api.v1.endpoints.webhooks.publish_refund_confirmation_email", return_value=True)
    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_sends_via_kafka(self, mock_crud, mock_kafka):
        """Webhook refund email sends via Kafka first."""
        from app.api.v1.endpoints.webhooks import _send_refund_confirmation_email

        order = _make_order(guest_email="buyer@test.com", customer_name="Buyer Name")
        event = _make_event()
        refund = _make_refund(amount=5000, currency="USD")

        mock_crud.order.get_with_items.return_value = order
        mock_crud.event.get.return_value = event

        run_async(_send_refund_confirmation_email(self.mock_db, refund))

        mock_kafka.assert_called_once()
        call_kwargs = mock_kafka.call_args.kwargs
        assert call_kwargs["to_email"] == "buyer@test.com"
        assert call_kwargs["refund_amount_cents"] == 5000

    @patch("app.api.v1.endpoints.webhooks.send_refund_confirmation_email")
    @patch("app.api.v1.endpoints.webhooks.publish_refund_confirmation_email", return_value=False)
    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_falls_back_to_direct_on_kafka_failure(self, mock_crud, mock_kafka, mock_direct):
        """Webhook refund email falls back to direct send when Kafka fails."""
        from app.api.v1.endpoints.webhooks import _send_refund_confirmation_email

        order = _make_order(guest_email="buyer@test.com", customer_name="Buyer")
        event = _make_event()
        refund = _make_refund(amount=3000, currency="USD")

        mock_crud.order.get_with_items.return_value = order
        mock_crud.event.get.return_value = event

        run_async(_send_refund_confirmation_email(self.mock_db, refund))

        mock_direct.assert_called_once()

    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_skips_email_when_no_buyer_email(self, mock_crud):
        """Skips email when no buyer email is available."""
        from app.api.v1.endpoints.webhooks import _send_refund_confirmation_email

        order = _make_order(guest_email="", user_id=None)
        event = _make_event()
        refund = _make_refund()

        mock_crud.order.get_with_items.return_value = order
        mock_crud.event.get.return_value = event

        with patch(
            "app.api.v1.endpoints.webhooks.publish_refund_confirmation_email"
        ) as mock_kafka:
            run_async(_send_refund_confirmation_email(self.mock_db, refund))

        mock_kafka.assert_not_called()

    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_handles_order_not_found(self, mock_crud):
        """Handles missing order gracefully without raising."""
        from app.api.v1.endpoints.webhooks import _send_refund_confirmation_email

        mock_crud.order.get_with_items.return_value = None
        refund = _make_refund()

        # Should not raise
        run_async(_send_refund_confirmation_email(self.mock_db, refund))

    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_handles_exception_without_propagating(self, mock_crud):
        """Exceptions are caught and do not propagate from webhook email sending."""
        from app.api.v1.endpoints.webhooks import _send_refund_confirmation_email

        mock_crud.order.get_with_items.side_effect = Exception("DB error")
        refund = _make_refund()

        # Should not raise
        run_async(_send_refund_confirmation_email(self.mock_db, refund))

    @patch("app.api.v1.endpoints.webhooks.get_user_info_async", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.webhooks.publish_refund_confirmation_email", return_value=True)
    @patch("app.api.v1.endpoints.webhooks.crud")
    def test_fetches_user_email_when_guest_email_empty(self, mock_crud, mock_kafka, mock_user_info):
        """Fetches email from user service when guest_email is empty but user_id exists."""
        from app.api.v1.endpoints.webhooks import _send_refund_confirmation_email

        order = _make_order(guest_email="", user_id="user_123")
        event = _make_event()
        refund = _make_refund(amount=5000, currency="USD")

        mock_crud.order.get_with_items.return_value = order
        mock_crud.event.get.return_value = event
        mock_user_info.return_value = {"email": "user@fetched.com", "name": "Fetched"}

        run_async(_send_refund_confirmation_email(self.mock_db, refund))

        mock_user_info.assert_awaited_once_with("user_123")
        mock_kafka.assert_called_once()
        assert mock_kafka.call_args.kwargs["to_email"] == "user@fetched.com"
