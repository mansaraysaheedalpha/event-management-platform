"""
Tests for the Stripe Connect service.

Verifies that StripeConnectService correctly:
- Creates Express connected accounts and stores settings in DB
- Generates onboarding and login links
- Retrieves account status and syncs with Stripe
- Retrieves account balances
- Updates payout schedules
- Deauthorizes accounts
- Handles webhook events (account.updated, payout.paid, payout.failed)
- Handles Stripe API errors gracefully

All Stripe API calls are mocked -- no real Stripe calls are ever made.
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timezone

from app.services.payment.stripe_connect_service import StripeConnectService
from app.services.payment.providers.stripe_provider import PaymentError


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
    # Ensure attribute access works for all fields
    for key, val in defaults.items():
        setattr(mock, key, val)
    return mock


class TestStripeConnectService:
    """Tests for Stripe Connect account management."""

    def setup_method(self):
        """Create a StripeConnectService with mocked stripe.api_key."""
        with patch("app.services.payment.stripe_connect_service.settings") as mock_settings:
            mock_settings.STRIPE_SECRET_KEY = "sk_test_fake"
            mock_settings.PLATFORM_NAME = "TestPlatform"
            mock_settings.PLATFORM_FEE_PERCENT = 4.0
            mock_settings.PLATFORM_FEE_FIXED_CENTS = 75
            mock_settings.FRONTEND_URL = "https://test.example.com"
            mock_settings.STRIPE_CONNECT_CLIENT_ID = "ca_test123"
            self.service = StripeConnectService()

    # ------------------------------------------------------------------ #
    # Account creation
    # ------------------------------------------------------------------ #

    @patch("app.services.payment.stripe_connect_service.stripe.AccountLink.create")
    @patch("app.services.payment.stripe_connect_service.stripe.Account.create")
    def test_create_connected_account_success(self, mock_account_create, mock_link_create):
        """Successfully creates Express account and stores in DB."""
        # Mock Stripe API responses
        mock_account = MagicMock()
        mock_account.id = "acct_new123"
        mock_account.charges_enabled = False
        mock_account.payouts_enabled = False
        mock_account.details_submitted = False
        mock_account_create.return_value = mock_account

        mock_link = MagicMock()
        mock_link.url = "https://connect.stripe.com/onboarding/test"
        mock_link_create.return_value = mock_link

        # Mock DB
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock PaymentProvider lookup
        mock_provider = MagicMock()
        mock_provider.id = "prov_stripe"
        with patch(
            "app.services.payment.stripe_connect_service.settings"
        ) as mock_settings:
            mock_settings.STRIPE_SECRET_KEY = "sk_test_fake"
            mock_settings.PLATFORM_NAME = "TestPlatform"
            mock_settings.PLATFORM_FEE_PERCENT = 4.0
            mock_settings.PLATFORM_FEE_FIXED_CENTS = 75
            mock_settings.FRONTEND_URL = "https://test.example.com"

            # Patch the PaymentProvider query
            def side_effect_query(model):
                query_mock = MagicMock()
                if model.__name__ == "OrganizationPaymentSettings":
                    query_mock.filter.return_value.first.return_value = None
                elif model.__name__ == "PaymentProvider":
                    query_mock.filter.return_value.first.return_value = mock_provider
                return query_mock

            mock_db.query.side_effect = side_effect_query

            result = run_async(
                self.service.create_connected_account(
                    organization_id="org_new",
                    organization_name="Test Org",
                    email="test@example.com",
                    country="US",
                    db=mock_db,
                )
            )

        assert result["account_id"] == "acct_new123"
        assert result["onboarding_url"] == "https://connect.stripe.com/onboarding/test"
        mock_account_create.assert_called_once()
        mock_db.commit.assert_called()

    @patch("app.services.payment.stripe_connect_service.stripe.Account.create")
    def test_create_connected_account_already_exists(self, mock_create):
        """Raises PaymentError when org already has an active connected account."""
        existing = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        with pytest.raises(PaymentError) as exc_info:
            run_async(
                self.service.create_connected_account(
                    organization_id="org_123",
                    organization_name="Existing Org",
                    email="test@example.com",
                    country="US",
                    db=mock_db,
                )
            )

        assert exc_info.value.code == "ACCOUNT_EXISTS"
        assert exc_info.value.retryable is False
        mock_create.assert_not_called()

    # ------------------------------------------------------------------ #
    # Onboarding links
    # ------------------------------------------------------------------ #

    @patch("app.services.payment.stripe_connect_service.stripe.AccountLink.create")
    def test_create_onboarding_link_success(self, mock_link_create):
        """Generates onboarding link for connected account."""
        mock_link = MagicMock()
        mock_link.url = "https://connect.stripe.com/onboarding/link"
        mock_link.expires_at = 1700000000
        mock_link_create.return_value = mock_link

        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        result = run_async(
            self.service.create_onboarding_link(
                organization_id="org_123",
                refresh_url="https://test.com/refresh",
                return_url="https://test.com/return",
                db=mock_db,
            )
        )

        assert result["url"] == "https://connect.stripe.com/onboarding/link"
        assert "expires_at" in result
        mock_link_create.assert_called_once_with(
            account="acct_test123",
            refresh_url="https://test.com/refresh",
            return_url="https://test.com/return",
            type="account_onboarding",
        )

    def test_create_onboarding_link_no_account(self):
        """Raises PaymentError when org has no connected account."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(PaymentError) as exc_info:
            run_async(
                self.service.create_onboarding_link(
                    organization_id="org_no_account",
                    refresh_url="https://test.com/refresh",
                    return_url="https://test.com/return",
                    db=mock_db,
                )
            )

        assert exc_info.value.code == "NO_CONNECTED_ACCOUNT"

    # ------------------------------------------------------------------ #
    # Login links
    # ------------------------------------------------------------------ #

    @patch("app.services.payment.stripe_connect_service.stripe.Account.create_login_link")
    def test_create_login_link_success(self, mock_login_link):
        """Generates Express dashboard login link."""
        mock_link = MagicMock()
        mock_link.url = "https://connect.stripe.com/express/login"
        mock_login_link.return_value = mock_link

        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        result = run_async(
            self.service.create_login_link(
                organization_id="org_123",
                db=mock_db,
            )
        )

        assert result == "https://connect.stripe.com/express/login"
        mock_login_link.assert_called_once_with("acct_test123")

    def test_create_login_link_no_account(self):
        """Raises PaymentError when org has no connected account."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(PaymentError) as exc_info:
            run_async(
                self.service.create_login_link(
                    organization_id="org_none",
                    db=mock_db,
                )
            )

        assert exc_info.value.code == "NO_CONNECTED_ACCOUNT"

    @patch("app.services.payment.stripe_connect_service.stripe.Account.create_login_link")
    def test_create_login_link_stripe_invalid_request(self, mock_login_link):
        """Raises PaymentError with ACCOUNT_NOT_READY when Stripe rejects the request."""
        import stripe

        mock_login_link.side_effect = stripe.error.InvalidRequestError(
            message="Account not onboarded", param=None
        )

        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        with pytest.raises(PaymentError) as exc_info:
            run_async(
                self.service.create_login_link(
                    organization_id="org_123",
                    db=mock_db,
                )
            )

        assert exc_info.value.code == "ACCOUNT_NOT_READY"

    # ------------------------------------------------------------------ #
    # Account status
    # ------------------------------------------------------------------ #

    @patch("app.services.payment.stripe_connect_service.stripe.Account.retrieve")
    def test_get_account_status_verified(self, mock_retrieve):
        """Returns verified=True when charges_enabled and payouts_enabled."""
        mock_account = MagicMock()
        mock_account.id = "acct_test123"
        mock_account.charges_enabled = True
        mock_account.payouts_enabled = True
        mock_account.details_submitted = True
        mock_account.requirements = None
        mock_retrieve.return_value = mock_account

        org_settings = _make_org_settings(verified_at=None, onboarding_completed_at=None)
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        result = run_async(
            self.service.get_account_status(
                organization_id="org_123",
                db=mock_db,
            )
        )

        assert result["is_connected"] is True
        assert result["charges_enabled"] is True
        assert result["payouts_enabled"] is True
        assert result["verified"] is True
        mock_db.commit.assert_called()

    @patch("app.services.payment.stripe_connect_service.stripe.Account.retrieve")
    def test_get_account_status_pending(self, mock_retrieve):
        """Returns verified=False with requirements when not fully verified."""
        mock_account = MagicMock()
        mock_account.id = "acct_test123"
        mock_account.charges_enabled = False
        mock_account.payouts_enabled = False
        mock_account.details_submitted = False
        mock_requirements = MagicMock()
        mock_requirements.currently_due = ["individual.verification.document"]
        mock_requirements.eventually_due = ["company.tax_id"]
        mock_requirements.past_due = []
        mock_requirements.disabled_reason = "requirements.pending_verification"
        mock_account.requirements = mock_requirements
        mock_retrieve.return_value = mock_account

        org_settings = _make_org_settings(
            charges_enabled=False,
            payouts_enabled=False,
            details_submitted=False,
            verified_at=None,
        )
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        result = run_async(
            self.service.get_account_status(
                organization_id="org_123",
                db=mock_db,
            )
        )

        assert result["is_connected"] is True
        assert result["verified"] is False
        assert result["requirements"] is not None
        assert "individual.verification.document" in result["requirements"]["currently_due"]

    def test_get_account_status_no_account(self):
        """Returns is_connected=False when org has no connected account."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = run_async(
            self.service.get_account_status(
                organization_id="org_none",
                db=mock_db,
            )
        )

        assert result["is_connected"] is False
        assert result["verified"] is False
        assert result["account_id"] is None

    # ------------------------------------------------------------------ #
    # Balance
    # ------------------------------------------------------------------ #

    @patch("app.services.payment.stripe_connect_service.stripe.Balance.retrieve")
    def test_get_account_balance(self, mock_balance):
        """Returns available and pending balances."""
        available_entry = MagicMock()
        available_entry.amount = 50000
        available_entry.currency = "usd"

        pending_entry = MagicMock()
        pending_entry.amount = 12000
        pending_entry.currency = "usd"

        mock_balance_obj = MagicMock()
        mock_balance_obj.available = [available_entry]
        mock_balance_obj.pending = [pending_entry]
        mock_balance.return_value = mock_balance_obj

        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        result = run_async(
            self.service.get_account_balance(
                organization_id="org_123",
                db=mock_db,
            )
        )

        assert result["available"] == [{"amount": 50000, "currency": "USD"}]
        assert result["pending"] == [{"amount": 12000, "currency": "USD"}]
        mock_balance.assert_called_once_with(stripe_account="acct_test123")

    def test_get_account_balance_no_account(self):
        """Raises PaymentError when org has no connected account."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(PaymentError) as exc_info:
            run_async(
                self.service.get_account_balance(
                    organization_id="org_none",
                    db=mock_db,
                )
            )

        assert exc_info.value.code == "NO_CONNECTED_ACCOUNT"

    # ------------------------------------------------------------------ #
    # Payout schedule
    # ------------------------------------------------------------------ #

    @patch("app.services.payment.stripe_connect_service.stripe.Account.modify")
    def test_update_payout_schedule_daily(self, mock_modify):
        """Updates payout schedule to daily."""
        mock_schedule = MagicMock()
        mock_schedule.interval = "daily"
        mock_account = MagicMock()
        mock_account.settings.payouts.schedule = mock_schedule
        mock_modify.return_value = mock_account

        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        result = run_async(
            self.service.update_payout_schedule(
                organization_id="org_123",
                interval="daily",
                weekly_anchor=None,
                monthly_anchor=None,
                db=mock_db,
            )
        )

        assert result["interval"] == "daily"
        mock_modify.assert_called_once_with(
            "acct_test123",
            settings={"payouts": {"schedule": {"interval": "daily"}}},
        )
        mock_db.commit.assert_called()

    @patch("app.services.payment.stripe_connect_service.stripe.Account.modify")
    def test_update_payout_schedule_weekly(self, mock_modify):
        """Updates payout schedule to weekly with anchor day."""
        mock_schedule = MagicMock()
        mock_schedule.interval = "weekly"
        mock_schedule.weekly_anchor = "monday"
        mock_account = MagicMock()
        mock_account.settings.payouts.schedule = mock_schedule
        mock_modify.return_value = mock_account

        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        result = run_async(
            self.service.update_payout_schedule(
                organization_id="org_123",
                interval="weekly",
                weekly_anchor="monday",
                monthly_anchor=None,
                db=mock_db,
            )
        )

        assert result["interval"] == "weekly"
        mock_modify.assert_called_once_with(
            "acct_test123",
            settings={
                "payouts": {
                    "schedule": {"interval": "weekly", "weekly_anchor": "monday"}
                }
            },
        )

    def test_update_payout_schedule_no_account(self):
        """Raises PaymentError when org has no connected account."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(PaymentError) as exc_info:
            run_async(
                self.service.update_payout_schedule(
                    organization_id="org_none",
                    interval="daily",
                    weekly_anchor=None,
                    monthly_anchor=None,
                    db=mock_db,
                )
            )

        assert exc_info.value.code == "NO_CONNECTED_ACCOUNT"

    # ------------------------------------------------------------------ #
    # Deauthorize
    # ------------------------------------------------------------------ #

    @patch("app.services.payment.stripe_connect_service.stripe.OAuth.deauthorize")
    def test_deauthorize_account(self, mock_deauth):
        """Disconnects account and marks inactive."""
        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        with patch("app.services.payment.stripe_connect_service.settings") as mock_s:
            mock_s.STRIPE_CONNECT_CLIENT_ID = "ca_test123"

            run_async(
                self.service.deauthorize_account(
                    organization_id="org_123",
                    db=mock_db,
                )
            )

        mock_deauth.assert_called_once()
        assert org_settings.is_active is False
        assert org_settings.charges_enabled is False
        assert org_settings.payouts_enabled is False
        assert org_settings.verified_at is None
        assert org_settings.deauthorized_at is not None
        mock_db.commit.assert_called()

    @patch("app.services.payment.stripe_connect_service.stripe.OAuth.deauthorize")
    def test_deauthorize_account_stripe_invalid_request_still_deactivates(self, mock_deauth):
        """Even if Stripe raises InvalidRequestError, the account is marked inactive."""
        import stripe

        mock_deauth.side_effect = stripe.error.InvalidRequestError(
            message="Account already deauthorized", param=None
        )

        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        with patch("app.services.payment.stripe_connect_service.settings") as mock_s:
            mock_s.STRIPE_CONNECT_CLIENT_ID = "ca_test123"

            # Should NOT raise, despite Stripe error
            run_async(
                self.service.deauthorize_account(
                    organization_id="org_123",
                    db=mock_db,
                )
            )

        assert org_settings.is_active is False
        mock_db.commit.assert_called()

    def test_deauthorize_account_no_account(self):
        """Raises PaymentError when org has no connected account."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(PaymentError) as exc_info:
            run_async(
                self.service.deauthorize_account(
                    organization_id="org_none",
                    db=mock_db,
                )
            )

        assert exc_info.value.code == "NO_CONNECTED_ACCOUNT"

    # ------------------------------------------------------------------ #
    # Webhook handlers
    # ------------------------------------------------------------------ #

    def test_handle_account_updated_enables_charges(self):
        """Updates charges_enabled when account.updated received."""
        org_settings = _make_org_settings(
            charges_enabled=False,
            payouts_enabled=False,
            details_submitted=False,
            verified_at=None,
            onboarding_completed_at=None,
        )
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        account_data = {
            "id": "acct_test123",
            "charges_enabled": True,
            "payouts_enabled": True,
            "details_submitted": True,
            "requirements": {
                "currently_due": [],
                "eventually_due": [],
                "past_due": [],
                "disabled_reason": None,
            },
        }

        run_async(
            self.service.handle_account_updated(
                account_data=account_data,
                db=mock_db,
            )
        )

        assert org_settings.charges_enabled is True
        assert org_settings.payouts_enabled is True
        assert org_settings.details_submitted is True
        assert org_settings.verified_at is not None
        assert org_settings.onboarding_completed_at is not None
        mock_db.commit.assert_called()

    def test_handle_account_updated_unknown_account(self):
        """Silently ignores updates for unknown accounts."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        account_data = {"id": "acct_unknown", "charges_enabled": True}

        # Should not raise
        run_async(
            self.service.handle_account_updated(
                account_data=account_data,
                db=mock_db,
            )
        )

        mock_db.commit.assert_not_called()

    def test_handle_account_updated_no_id(self):
        """Silently ignores event without account ID."""
        mock_db = MagicMock()

        run_async(
            self.service.handle_account_updated(
                account_data={},
                db=mock_db,
            )
        )

        mock_db.commit.assert_not_called()

    def test_handle_account_updated_clears_verified_when_disabled(self):
        """Clears verified_at when charges or payouts become disabled."""
        org_settings = _make_org_settings(
            charges_enabled=True,
            payouts_enabled=True,
            verified_at=datetime.now(timezone.utc),
        )
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        account_data = {
            "id": "acct_test123",
            "charges_enabled": False,  # Now disabled
            "payouts_enabled": True,
            "details_submitted": True,
            "requirements": {},
        }

        run_async(
            self.service.handle_account_updated(
                account_data=account_data,
                db=mock_db,
            )
        )

        assert org_settings.charges_enabled is False
        assert org_settings.verified_at is None

    def test_handle_payout_paid(self):
        """Records successful payout in organizer_payouts table."""
        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings
        # No existing payout record
        mock_db.execute.return_value.fetchone.return_value = None

        payout_data = {
            "id": "po_test_123",
            "account": "acct_test123",
            "amount": 50000,
            "currency": "usd",
            "arrival_date": 1700000000,
            "failure_code": None,
            "failure_message": None,
        }

        run_async(
            self.service.handle_payout_event(
                payout_data=payout_data,
                event_type="payout.paid",
                db=mock_db,
            )
        )

        mock_db.commit.assert_called()
        # Verify INSERT was called (second execute call, after the SELECT)
        calls = mock_db.execute.call_args_list
        assert len(calls) >= 2
        # The second call should be the INSERT
        insert_args = calls[1]
        insert_params = insert_args[0][1]  # second positional arg
        assert insert_params["amount"] == 50000
        assert insert_params["status"] == "paid"
        assert insert_params["currency"] == "USD"

    def test_handle_payout_failed(self):
        """Records failed payout with error details."""
        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings
        mock_db.execute.return_value.fetchone.return_value = None

        payout_data = {
            "id": "po_fail_123",
            "account": "acct_test123",
            "amount": 25000,
            "currency": "usd",
            "arrival_date": None,
            "failure_code": "account_closed",
            "failure_message": "The bank account has been closed.",
        }

        run_async(
            self.service.handle_payout_event(
                payout_data=payout_data,
                event_type="payout.failed",
                db=mock_db,
            )
        )

        mock_db.commit.assert_called()
        calls = mock_db.execute.call_args_list
        assert len(calls) >= 2
        insert_params = calls[1][0][1]
        assert insert_params["status"] == "failed"
        assert insert_params["failure_code"] == "account_closed"
        assert insert_params["failure_message"] == "The bank account has been closed."

    def test_handle_payout_idempotent_update(self):
        """Processing same payout twice updates existing record instead of inserting."""
        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings
        # Existing payout record found
        mock_db.execute.return_value.fetchone.return_value = MagicMock(id="po_existing")

        payout_data = {
            "id": "po_existing_stripe",
            "account": "acct_test123",
            "amount": 50000,
            "currency": "usd",
            "arrival_date": None,
            "failure_code": None,
            "failure_message": None,
        }

        run_async(
            self.service.handle_payout_event(
                payout_data=payout_data,
                event_type="payout.paid",
                db=mock_db,
            )
        )

        mock_db.commit.assert_called()
        # Should only have SELECT + UPDATE (not INSERT)
        calls = mock_db.execute.call_args_list
        assert len(calls) == 2  # SELECT + UPDATE

    def test_handle_payout_no_id(self):
        """Silently ignores event without payout ID."""
        mock_db = MagicMock()

        run_async(
            self.service.handle_payout_event(
                payout_data={},
                event_type="payout.paid",
                db=mock_db,
            )
        )

        mock_db.commit.assert_not_called()

    # ------------------------------------------------------------------ #
    # Error handling
    # ------------------------------------------------------------------ #

    @patch("app.services.payment.stripe_connect_service.stripe.Account.create")
    def test_stripe_error_handling(self, mock_create):
        """Handles stripe.error.StripeError gracefully."""
        import stripe

        mock_create.side_effect = stripe.error.StripeError(
            message="Stripe API down"
        )

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(PaymentError) as exc_info:
            run_async(
                self.service.create_connected_account(
                    organization_id="org_err",
                    organization_name="Err Org",
                    email="err@example.com",
                    country="US",
                    db=mock_db,
                )
            )

        assert exc_info.value.code == "PROVIDER_ERROR"
        assert exc_info.value.retryable is True

    @patch("app.services.payment.stripe_connect_service.stripe.Balance.retrieve")
    def test_balance_stripe_error(self, mock_balance):
        """Handles Stripe error when retrieving balance."""
        import stripe

        mock_balance.side_effect = stripe.error.StripeError(message="API error")

        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        with pytest.raises(PaymentError) as exc_info:
            run_async(
                self.service.get_account_balance(
                    organization_id="org_123",
                    db=mock_db,
                )
            )

        assert exc_info.value.code == "PROVIDER_ERROR"
        assert exc_info.value.retryable is True

    @patch("app.services.payment.stripe_connect_service.stripe.OAuth.deauthorize")
    def test_deauthorize_stripe_error_propagates(self, mock_deauth):
        """Handles generic StripeError during deauthorize (non-InvalidRequest)."""
        import stripe

        mock_deauth.side_effect = stripe.error.StripeError(
            message="Network error"
        )

        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        with patch("app.services.payment.stripe_connect_service.settings") as mock_s:
            mock_s.STRIPE_CONNECT_CLIENT_ID = "ca_test123"

            with pytest.raises(PaymentError) as exc_info:
                run_async(
                    self.service.deauthorize_account(
                        organization_id="org_123",
                        db=mock_db,
                    )
                )

        assert exc_info.value.code == "PROVIDER_ERROR"
