"""
Tests for the Stripe Connect webhook endpoint.

Verifies that the /webhooks/stripe-connect endpoint correctly:
- Validates Stripe-Signature headers and webhook secrets
- Processes account.updated, account.application.deauthorized,
  payout.paid, payout.failed, and capability.updated events
- Enforces idempotency (skips already-processed events)
- Sends appropriate email notifications (via Kafka or direct fallback)
- Returns 200 on processing errors to prevent Stripe retries
- Marks events as failed when processing errors occur

Also tests the internal helper functions directly:
- _handle_account_deauthorized
- _send_account_status_emails
- _send_payout_emails
- _handle_capability_updated

All Stripe API calls and external services are mocked.
"""

import asyncio
import pytest
import stripe
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_async(coro):
    """Helper to run async coroutines in sync tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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


def _make_stripe_event(
    event_id="evt_test_001",
    event_type="account.updated",
    data_object=None,
    account=None,
):
    """Create a mock Stripe event object."""
    event = MagicMock()
    event.id = event_id
    event.type = event_type
    event.account = account
    event.data.object = data_object or {}
    event.to_dict.return_value = {
        "id": event_id,
        "type": event_type,
        "data": {"object": data_object or {}},
    }
    return event


# ---------------------------------------------------------------------------
# Module path constants for patching
# ---------------------------------------------------------------------------
WEBHOOK_MODULE = "app.api.v1.endpoints.connect_webhooks"


# ---------------------------------------------------------------------------
# Local test_client fixture that avoids remote DB connections
# ---------------------------------------------------------------------------
@pytest.fixture(scope="function")
def webhook_client():
    """
    Provides a TestClient with mocked DB, auth, and Kafka.
    Patches the DB engine to prevent the lifespan handler from connecting
    to the remote database.
    """
    from app.main import app
    from app.api import deps
    from app.db.session import get_db
    from app.core.kafka_producer import get_kafka_producer

    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[deps.get_current_user] = lambda: MagicMock(
        sub="user_123", org_id="org_abc"
    )
    app.dependency_overrides[get_kafka_producer] = lambda: MagicMock()

    # Patch the engine so the lifespan create_all does not hit a real DB
    with patch("app.main.engine"), patch("app.main.Base"):
        with TestClient(app) as client:
            yield client

    app.dependency_overrides.clear()


# =========================================================================== #
# 1. Signature Verification
# =========================================================================== #


class TestSignatureVerification:
    """Tests for webhook signature and secret validation."""

    def test_missing_stripe_signature_returns_400(self, webhook_client):
        """Missing Stripe-Signature header returns 400."""
        response = webhook_client.post(
            "/api/v1/webhooks/stripe-connect",
            content=b'{"test": true}',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400
        assert "Missing signature" in response.json()["detail"]

    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_invalid_signature_returns_400(self, mock_settings, webhook_client):
        """Invalid signature returns 400."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test_secret"

        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.side_effect = stripe.error.SignatureVerificationError(
                message="Invalid signature", sig_header="bad_sig"
            )
            response = webhook_client.post(
                "/api/v1/webhooks/stripe-connect",
                content=b'{"test": true}',
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "bad_sig",
                },
            )

        assert response.status_code == 400
        assert "Invalid signature" in response.json()["detail"]

    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_missing_webhook_secret_returns_500(self, mock_settings, webhook_client):
        """Missing STRIPE_CONNECT_WEBHOOK_SECRET returns 500."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = None

        response = webhook_client.post(
            "/api/v1/webhooks/stripe-connect",
            content=b'{"test": true}',
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "t=123,v1=abc",
            },
        )

        assert response.status_code == 500
        assert "Webhook secret not configured" in response.json()["detail"]

    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_invalid_payload_returns_400(self, mock_settings, webhook_client):
        """Invalid JSON payload returns 400."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test_secret"

        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.side_effect = ValueError("Invalid payload")
            response = webhook_client.post(
                "/api/v1/webhooks/stripe-connect",
                content=b"not json",
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

        assert response.status_code == 400
        assert "Invalid payload" in response.json()["detail"]


# =========================================================================== #
# 2. Event Processing
# =========================================================================== #


class TestEventProcessing:
    """Tests for processing different event types via the HTTP endpoint."""

    @patch(f"{WEBHOOK_MODULE}._send_account_status_emails", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.StripeConnectService")
    @patch(f"{WEBHOOK_MODULE}.crud")
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_account_updated_calls_handler_and_emails(
        self, mock_settings, mock_crud, mock_service_cls, mock_send_emails, webhook_client
    ):
        """account.updated event calls handle_account_updated and triggers emails."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test"
        account_data = {"id": "acct_test123", "charges_enabled": True}
        event = _make_stripe_event(
            event_type="account.updated", data_object=account_data
        )

        mock_crud.webhook_event.is_already_processed.return_value = False
        mock_webhook_event = MagicMock()
        mock_webhook_event.id = "whe_1"
        mock_crud.webhook_event.upsert_event.return_value = mock_webhook_event

        mock_service = MagicMock()
        mock_service.handle_account_updated = AsyncMock()
        mock_service_cls.return_value = mock_service

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = webhook_client.post(
                "/api/v1/webhooks/stripe-connect",
                content=b'{"test": true}',
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "processed"
        mock_service.handle_account_updated.assert_awaited_once()
        mock_send_emails.assert_awaited_once()
        # Verify the account_data dict was passed as first arg
        assert mock_send_emails.call_args[0][0] == account_data

    @patch(f"{WEBHOOK_MODULE}._handle_account_deauthorized", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.crud")
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_account_deauthorized_calls_handler(
        self, mock_settings, mock_crud, mock_handle_deauth, webhook_client
    ):
        """account.application.deauthorized calls _handle_account_deauthorized."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test"
        account_data = {"id": "acct_test123"}
        event = _make_stripe_event(
            event_type="account.application.deauthorized", data_object=account_data
        )

        mock_crud.webhook_event.is_already_processed.return_value = False
        mock_webhook_event = MagicMock()
        mock_webhook_event.id = "whe_2"
        mock_crud.webhook_event.upsert_event.return_value = mock_webhook_event

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = webhook_client.post(
                "/api/v1/webhooks/stripe-connect",
                content=b'{"test": true}',
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "processed"
        mock_handle_deauth.assert_awaited_once()

    @patch(f"{WEBHOOK_MODULE}._send_payout_emails", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.StripeConnectService")
    @patch(f"{WEBHOOK_MODULE}.crud")
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_payout_paid_logs_and_sends_email(
        self, mock_settings, mock_crud, mock_service_cls, mock_send_emails, webhook_client
    ):
        """payout.paid event calls handle_payout_event and sends payout email."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test"
        payout_data = {"id": "po_123", "amount": 50000, "currency": "usd"}
        event = _make_stripe_event(
            event_type="payout.paid",
            data_object=payout_data,
            account="acct_connected_456",
        )

        mock_crud.webhook_event.is_already_processed.return_value = False
        mock_webhook_event = MagicMock()
        mock_webhook_event.id = "whe_3"
        mock_crud.webhook_event.upsert_event.return_value = mock_webhook_event

        mock_service = MagicMock()
        mock_service.handle_payout_event = AsyncMock()
        mock_service_cls.return_value = mock_service

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = webhook_client.post(
                "/api/v1/webhooks/stripe-connect",
                content=b'{"test": true}',
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "processed"
        mock_service.handle_payout_event.assert_awaited_once()
        # Verify account field was added to payout_data
        call_kwargs = mock_service.handle_payout_event.call_args[1]
        assert call_kwargs["payout_data"].get("account") == "acct_connected_456"
        mock_send_emails.assert_awaited_once()

    @patch(f"{WEBHOOK_MODULE}._send_payout_emails", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.StripeConnectService")
    @patch(f"{WEBHOOK_MODULE}.crud")
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_payout_failed_logs_and_sends_email(
        self, mock_settings, mock_crud, mock_service_cls, mock_send_emails, webhook_client
    ):
        """payout.failed event calls handle_payout_event and sends payout email."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test"
        payout_data = {
            "id": "po_fail_123",
            "amount": 25000,
            "currency": "usd",
            "failure_code": "account_closed",
            "failure_message": "Bank account closed",
        }
        event = _make_stripe_event(
            event_type="payout.failed",
            data_object=payout_data,
            account="acct_connected_789",
        )

        mock_crud.webhook_event.is_already_processed.return_value = False
        mock_webhook_event = MagicMock()
        mock_webhook_event.id = "whe_4"
        mock_crud.webhook_event.upsert_event.return_value = mock_webhook_event

        mock_service = MagicMock()
        mock_service.handle_payout_event = AsyncMock()
        mock_service_cls.return_value = mock_service

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = webhook_client.post(
                "/api/v1/webhooks/stripe-connect",
                content=b'{"test": true}',
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "processed"
        mock_service.handle_payout_event.assert_awaited_once()
        call_kwargs = mock_service.handle_payout_event.call_args[1]
        assert call_kwargs["event_type"] == "payout.failed"
        mock_send_emails.assert_awaited_once()

    @patch(f"{WEBHOOK_MODULE}._handle_capability_updated", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.crud")
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_capability_updated_calls_handler(
        self, mock_settings, mock_crud, mock_handle_cap, webhook_client
    ):
        """capability.updated event calls _handle_capability_updated."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test"
        cap_data = {
            "id": "card_payments",
            "account": "acct_test123",
            "status": "inactive",
        }
        event = _make_stripe_event(
            event_type="capability.updated", data_object=cap_data
        )

        mock_crud.webhook_event.is_already_processed.return_value = False
        mock_webhook_event = MagicMock()
        mock_webhook_event.id = "whe_5"
        mock_crud.webhook_event.upsert_event.return_value = mock_webhook_event

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = webhook_client.post(
                "/api/v1/webhooks/stripe-connect",
                content=b'{"test": true}',
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "processed"
        mock_handle_cap.assert_awaited_once()

    @patch(f"{WEBHOOK_MODULE}.crud")
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_unknown_event_type_returns_ok(self, mock_settings, mock_crud, webhook_client):
        """Unknown event types are logged and returned with status=processed."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test"
        event = _make_stripe_event(
            event_type="some.unknown.event", data_object={"id": "xyz"}
        )

        mock_crud.webhook_event.is_already_processed.return_value = False
        mock_webhook_event = MagicMock()
        mock_webhook_event.id = "whe_6"
        mock_crud.webhook_event.upsert_event.return_value = mock_webhook_event

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = webhook_client.post(
                "/api/v1/webhooks/stripe-connect",
                content=b'{"test": true}',
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "processed"
        mock_crud.webhook_event.mark_processed.assert_called_once()


# =========================================================================== #
# 3. Idempotency
# =========================================================================== #


class TestIdempotency:
    """Tests for idempotent event processing."""

    @patch(f"{WEBHOOK_MODULE}.crud")
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_already_processed_event_returns_already_processed(
        self, mock_settings, mock_crud, webhook_client
    ):
        """Already-processed event returns status='already_processed'."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test"
        event = _make_stripe_event(event_id="evt_duplicate")

        mock_crud.webhook_event.is_already_processed.return_value = True

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = webhook_client.post(
                "/api/v1/webhooks/stripe-connect",
                content=b'{"test": true}',
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "already_processed"

    @patch(f"{WEBHOOK_MODULE}.crud")
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_same_event_id_not_processed_twice(
        self, mock_settings, mock_crud, webhook_client
    ):
        """Same event ID triggers is_already_processed check and skips reprocessing."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test"
        event = _make_stripe_event(event_id="evt_same_id")
        mock_crud.webhook_event.is_already_processed.return_value = True

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = webhook_client.post(
                "/api/v1/webhooks/stripe-connect",
                content=b'{"test": true}',
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

        assert response.json()["status"] == "already_processed"
        # Ensure we never get to upsert_event or mark_processing
        mock_crud.webhook_event.upsert_event.assert_not_called()
        mock_crud.webhook_event.mark_processing.assert_not_called()


# =========================================================================== #
# 4. Email Notifications - Direct Helper Tests
# =========================================================================== #


def _setup_email_test_db(org_settings):
    """Create a mock DB with OrganizationPaymentSettings and Event queries."""
    mock_db = MagicMock()
    mock_event = MagicMock()
    mock_event.owner_id = "user_owner_1"
    mock_event.name = "Test Event"
    mock_event.organization_id = "org_123"

    def query_side_effect(model):
        query_mock = MagicMock()
        if model.__name__ == "OrganizationPaymentSettings":
            query_mock.filter.return_value.first.return_value = org_settings
        elif model.__name__ == "Event":
            query_mock.filter.return_value.first.return_value = mock_event
        return query_mock

    mock_db.query.side_effect = query_side_effect
    return mock_db


class TestSendAccountStatusEmails:
    """Tests for the _send_account_status_emails helper function."""

    @patch(f"{WEBHOOK_MODULE}.send_stripe_connected_email")
    @patch(f"{WEBHOOK_MODULE}.publish_stripe_connected_email")
    @patch(f"{WEBHOOK_MODULE}.get_user_info_async", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_sends_stripe_connected_when_charges_enabled_and_recently_verified(
        self,
        mock_settings,
        mock_get_user,
        mock_kafka_connected,
        mock_direct_connected,
    ):
        """Sends stripe_connected email when charges_enabled=True and recently verified."""
        from app.api.v1.endpoints.connect_webhooks import _send_account_status_emails

        mock_settings.FRONTEND_URL = "https://test.example.com"
        mock_get_user.return_value = {"email": "org@test.com", "name": "Test Org Owner"}

        now = datetime.now(timezone.utc)
        org_settings = _make_org_settings(
            verified_at=now - timedelta(seconds=10),  # Verified 10 seconds ago
            charges_enabled=True,
        )
        mock_db = _setup_email_test_db(org_settings)
        mock_kafka_connected.return_value = True  # Kafka succeeds

        account_data = {
            "id": "acct_test123",
            "charges_enabled": True,
            "requirements": {"past_due": []},
        }

        run_async(_send_account_status_emails(account_data, mock_db))

        mock_kafka_connected.assert_called_once()
        # Direct email should NOT be called since Kafka succeeded
        mock_direct_connected.assert_not_called()

    @patch(f"{WEBHOOK_MODULE}.send_stripe_connected_email")
    @patch(f"{WEBHOOK_MODULE}.publish_stripe_connected_email")
    @patch(f"{WEBHOOK_MODULE}.get_user_info_async", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_falls_back_to_direct_email_when_kafka_fails(
        self,
        mock_settings,
        mock_get_user,
        mock_kafka_connected,
        mock_direct_connected,
    ):
        """Falls back to direct email send when Kafka publish returns False."""
        from app.api.v1.endpoints.connect_webhooks import _send_account_status_emails

        mock_settings.FRONTEND_URL = "https://test.example.com"
        mock_get_user.return_value = {"email": "org@test.com", "name": "Test Owner"}

        now = datetime.now(timezone.utc)
        org_settings = _make_org_settings(
            verified_at=now - timedelta(seconds=5),
            charges_enabled=True,
        )
        mock_db = _setup_email_test_db(org_settings)
        mock_kafka_connected.return_value = False  # Kafka fails

        account_data = {
            "id": "acct_test123",
            "charges_enabled": True,
            "requirements": {"past_due": []},
        }

        run_async(_send_account_status_emails(account_data, mock_db))

        mock_kafka_connected.assert_called_once()
        mock_direct_connected.assert_called_once()

    @patch(f"{WEBHOOK_MODULE}.send_stripe_restricted_email")
    @patch(f"{WEBHOOK_MODULE}.publish_stripe_restricted_email")
    @patch(f"{WEBHOOK_MODULE}.get_user_info_async", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_sends_stripe_restricted_when_past_due_requirements(
        self,
        mock_settings,
        mock_get_user,
        mock_kafka_restricted,
        mock_direct_restricted,
    ):
        """Sends stripe_restricted email when requirements.past_due has items."""
        from app.api.v1.endpoints.connect_webhooks import _send_account_status_emails

        mock_settings.FRONTEND_URL = "https://test.example.com"
        mock_get_user.return_value = {"email": "org@test.com", "name": "Owner"}

        # verified_at is old (won't trigger connected email)
        org_settings = _make_org_settings(
            verified_at=datetime.now(timezone.utc) - timedelta(hours=1),
            charges_enabled=True,
        )
        mock_db = _setup_email_test_db(org_settings)
        mock_kafka_restricted.return_value = True

        account_data = {
            "id": "acct_test123",
            "charges_enabled": True,
            "requirements": {
                "past_due": ["individual.verification.document"],
            },
        }

        run_async(_send_account_status_emails(account_data, mock_db))

        mock_kafka_restricted.assert_called_once()
        call_kwargs = mock_kafka_restricted.call_args
        assert call_kwargs[1]["requirements_past_due"] == [
            "individual.verification.document"
        ]

    @patch(f"{WEBHOOK_MODULE}.get_user_info_async", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_no_email_sent_when_no_org_settings(self, mock_settings, mock_get_user):
        """No email sent when org settings not found for account."""
        from app.api.v1.endpoints.connect_webhooks import _send_account_status_emails

        mock_settings.FRONTEND_URL = "https://test.example.com"
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        account_data = {"id": "acct_unknown", "charges_enabled": True}

        run_async(_send_account_status_emails(account_data, mock_db))
        mock_get_user.assert_not_called()

    @patch(f"{WEBHOOK_MODULE}.get_user_info_async", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_no_email_sent_when_no_email_found(self, mock_settings, mock_get_user):
        """No email sent when user info has no email."""
        from app.api.v1.endpoints.connect_webhooks import _send_account_status_emails

        mock_settings.FRONTEND_URL = "https://test.example.com"
        mock_get_user.return_value = {"email": "", "name": "No Email User"}

        org_settings = _make_org_settings()
        mock_db = _setup_email_test_db(org_settings)

        account_data = {
            "id": "acct_test123",
            "charges_enabled": True,
            "requirements": {"past_due": ["doc"]},
        }

        # Should not raise, just skip email
        run_async(_send_account_status_emails(account_data, mock_db))

    @patch(f"{WEBHOOK_MODULE}.send_stripe_connected_email")
    @patch(f"{WEBHOOK_MODULE}.publish_stripe_connected_email")
    @patch(f"{WEBHOOK_MODULE}.get_user_info_async", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_no_connected_email_when_verified_at_is_old(
        self,
        mock_settings,
        mock_get_user,
        mock_kafka_connected,
        mock_direct_connected,
    ):
        """Does not send stripe_connected if verified_at is older than 60 seconds."""
        from app.api.v1.endpoints.connect_webhooks import _send_account_status_emails

        mock_settings.FRONTEND_URL = "https://test.example.com"
        mock_get_user.return_value = {"email": "org@test.com", "name": "Owner"}

        # Verified 2 minutes ago -- too old
        org_settings = _make_org_settings(
            verified_at=datetime.now(timezone.utc) - timedelta(minutes=2),
            charges_enabled=True,
        )
        mock_db = _setup_email_test_db(org_settings)

        account_data = {
            "id": "acct_test123",
            "charges_enabled": True,
            "requirements": {"past_due": []},
        }

        run_async(_send_account_status_emails(account_data, mock_db))

        # Should NOT send connected email
        mock_kafka_connected.assert_not_called()
        mock_direct_connected.assert_not_called()

    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_no_email_when_account_id_empty(self, mock_settings):
        """No email sent when account_id is empty."""
        from app.api.v1.endpoints.connect_webhooks import _send_account_status_emails

        mock_settings.FRONTEND_URL = "https://test.example.com"
        mock_db = MagicMock()

        account_data = {"id": "", "charges_enabled": True}

        # Should return early without querying DB
        run_async(_send_account_status_emails(account_data, mock_db))
        mock_db.query.assert_not_called()


class TestSendPayoutEmails:
    """Tests for the _send_payout_emails helper function."""

    @patch(f"{WEBHOOK_MODULE}.send_payout_sent_email")
    @patch(f"{WEBHOOK_MODULE}.publish_payout_sent_email")
    @patch(f"{WEBHOOK_MODULE}.get_user_info_async", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_sends_payout_sent_email_for_paid(
        self,
        mock_settings,
        mock_get_user,
        mock_kafka_payout,
        mock_direct_payout,
    ):
        """Sends payout_sent email for payout.paid event."""
        from app.api.v1.endpoints.connect_webhooks import _send_payout_emails

        mock_settings.FRONTEND_URL = "https://test.example.com"
        mock_get_user.return_value = {"email": "org@test.com", "name": "Owner"}

        org_settings = _make_org_settings()
        mock_db = _setup_email_test_db(org_settings)
        mock_kafka_payout.return_value = True

        payout_data = {
            "account": "acct_test123",
            "amount": 50000,
            "currency": "usd",
            "arrival_date": 1700000000,
            "bank_account": {"last4": "4242"},
        }

        run_async(_send_payout_emails(payout_data, "payout.paid", mock_db))

        mock_kafka_payout.assert_called_once()
        call_kwargs = mock_kafka_payout.call_args[1]
        assert call_kwargs["payout_amount_cents"] == 50000
        assert call_kwargs["currency"] == "USD"
        assert call_kwargs["bank_last_four"] == "4242"
        assert call_kwargs["to_email"] == "org@test.com"
        # Direct email should NOT be called since Kafka succeeded
        mock_direct_payout.assert_not_called()

    @patch(f"{WEBHOOK_MODULE}.send_payout_failed_email")
    @patch(f"{WEBHOOK_MODULE}.publish_payout_failed_email")
    @patch(f"{WEBHOOK_MODULE}.get_user_info_async", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_sends_payout_failed_email_for_failed(
        self,
        mock_settings,
        mock_get_user,
        mock_kafka_failed,
        mock_direct_failed,
    ):
        """Sends payout_failed email for payout.failed event."""
        from app.api.v1.endpoints.connect_webhooks import _send_payout_emails

        mock_settings.FRONTEND_URL = "https://test.example.com"
        mock_get_user.return_value = {"email": "org@test.com", "name": "Owner"}

        org_settings = _make_org_settings()
        mock_db = _setup_email_test_db(org_settings)
        mock_kafka_failed.return_value = True

        payout_data = {
            "account": "acct_test123",
            "amount": 25000,
            "currency": "eur",
            "failure_code": "account_closed",
            "failure_message": "The bank account has been closed.",
        }

        run_async(_send_payout_emails(payout_data, "payout.failed", mock_db))

        mock_kafka_failed.assert_called_once()
        call_kwargs = mock_kafka_failed.call_args[1]
        assert call_kwargs["payout_amount_cents"] == 25000
        assert call_kwargs["currency"] == "EUR"
        assert call_kwargs["failure_reason"] == "The bank account has been closed."
        mock_direct_failed.assert_not_called()

    @patch(f"{WEBHOOK_MODULE}.send_payout_failed_email")
    @patch(f"{WEBHOOK_MODULE}.publish_payout_failed_email")
    @patch(f"{WEBHOOK_MODULE}.get_user_info_async", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_payout_failed_fallback_to_failure_code(
        self,
        mock_settings,
        mock_get_user,
        mock_kafka_failed,
        mock_direct_failed,
    ):
        """Uses failure_code as fallback when failure_message is empty."""
        from app.api.v1.endpoints.connect_webhooks import _send_payout_emails

        mock_settings.FRONTEND_URL = "https://test.example.com"
        mock_get_user.return_value = {"email": "org@test.com", "name": "Owner"}

        org_settings = _make_org_settings()
        mock_db = _setup_email_test_db(org_settings)
        mock_kafka_failed.return_value = True

        payout_data = {
            "account": "acct_test123",
            "amount": 10000,
            "currency": "usd",
            "failure_code": "insufficient_funds",
            "failure_message": "",  # Empty message
        }

        run_async(_send_payout_emails(payout_data, "payout.failed", mock_db))

        call_kwargs = mock_kafka_failed.call_args[1]
        assert call_kwargs["failure_reason"] == "insufficient_funds"

    @patch(f"{WEBHOOK_MODULE}.send_payout_failed_email")
    @patch(f"{WEBHOOK_MODULE}.publish_payout_failed_email")
    @patch(f"{WEBHOOK_MODULE}.get_user_info_async", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_payout_failed_default_failure_message(
        self,
        mock_settings,
        mock_get_user,
        mock_kafka_failed,
        mock_direct_failed,
    ):
        """Uses default message when both failure_code and failure_message are empty."""
        from app.api.v1.endpoints.connect_webhooks import _send_payout_emails

        mock_settings.FRONTEND_URL = "https://test.example.com"
        mock_get_user.return_value = {"email": "org@test.com", "name": "Owner"}

        org_settings = _make_org_settings()
        mock_db = _setup_email_test_db(org_settings)
        mock_kafka_failed.return_value = True

        payout_data = {
            "account": "acct_test123",
            "amount": 10000,
            "currency": "usd",
            "failure_code": "",
            "failure_message": "",
        }

        run_async(_send_payout_emails(payout_data, "payout.failed", mock_db))

        call_kwargs = mock_kafka_failed.call_args[1]
        assert (
            call_kwargs["failure_reason"]
            == "An unexpected error occurred with your payout"
        )

    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_no_payout_email_when_no_account_id(self, mock_settings):
        """No email sent when payout_data has no account field."""
        from app.api.v1.endpoints.connect_webhooks import _send_payout_emails

        mock_settings.FRONTEND_URL = "https://test.example.com"
        mock_db = MagicMock()

        payout_data = {"amount": 50000, "currency": "usd"}

        run_async(_send_payout_emails(payout_data, "payout.paid", mock_db))
        mock_db.query.assert_not_called()

    @patch(f"{WEBHOOK_MODULE}.send_payout_sent_email")
    @patch(f"{WEBHOOK_MODULE}.publish_payout_sent_email")
    @patch(f"{WEBHOOK_MODULE}.get_user_info_async", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_payout_email_kafka_failure_falls_back_to_direct(
        self,
        mock_settings,
        mock_get_user,
        mock_kafka_payout,
        mock_direct_payout,
    ):
        """Falls back to direct email when Kafka publish fails for payout."""
        from app.api.v1.endpoints.connect_webhooks import _send_payout_emails

        mock_settings.FRONTEND_URL = "https://test.example.com"
        mock_get_user.return_value = {"email": "org@test.com", "name": "Owner"}

        org_settings = _make_org_settings()
        mock_db = _setup_email_test_db(org_settings)
        mock_kafka_payout.return_value = False  # Kafka fails

        payout_data = {
            "account": "acct_test123",
            "amount": 50000,
            "currency": "usd",
            "arrival_date": 1700000000,
        }

        run_async(_send_payout_emails(payout_data, "payout.paid", mock_db))

        mock_kafka_payout.assert_called_once()
        mock_direct_payout.assert_called_once()


class TestEmailFailuresDontBreakWebhook:
    """Tests that email sending failures don't prevent webhook processing."""

    @patch(f"{WEBHOOK_MODULE}._send_account_status_emails", new_callable=AsyncMock)
    @patch(f"{WEBHOOK_MODULE}.StripeConnectService")
    @patch(f"{WEBHOOK_MODULE}.crud")
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_email_error_during_account_updated_still_returns_200(
        self, mock_settings, mock_crud, mock_service_cls, mock_send_emails, webhook_client
    ):
        """Email failure during account.updated still returns 200 (processing_error)."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test"
        event = _make_stripe_event(
            event_type="account.updated",
            data_object={"id": "acct_test123", "charges_enabled": True},
        )

        mock_crud.webhook_event.is_already_processed.return_value = False
        mock_webhook_event = MagicMock()
        mock_webhook_event.id = "whe_email_fail"
        mock_crud.webhook_event.upsert_event.return_value = mock_webhook_event

        mock_service = MagicMock()
        mock_service.handle_account_updated = AsyncMock()
        mock_service_cls.return_value = mock_service

        # Email sending raises an exception
        mock_send_emails.side_effect = Exception("SMTP connection failed")

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = webhook_client.post(
                "/api/v1/webhooks/stripe-connect",
                content=b'{"test": true}',
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

        # Should still return 200 to prevent Stripe retries
        assert response.status_code == 200
        assert response.json()["status"] == "processing_error"


# =========================================================================== #
# 5. Error Handling
# =========================================================================== #


class TestErrorHandling:
    """Tests for webhook error handling behavior."""

    @patch(f"{WEBHOOK_MODULE}.StripeConnectService")
    @patch(f"{WEBHOOK_MODULE}.crud")
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_processing_error_returns_200(
        self, mock_settings, mock_crud, mock_service_cls, webhook_client
    ):
        """Processing errors still return 200 to prevent Stripe retries."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test"
        event = _make_stripe_event(
            event_type="account.updated",
            data_object={"id": "acct_test123"},
        )

        mock_crud.webhook_event.is_already_processed.return_value = False
        mock_webhook_event = MagicMock()
        mock_webhook_event.id = "whe_err"
        mock_crud.webhook_event.upsert_event.return_value = mock_webhook_event

        mock_service = MagicMock()
        mock_service.handle_account_updated = AsyncMock(
            side_effect=Exception("DB connection lost")
        )
        mock_service_cls.return_value = mock_service

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = webhook_client.post(
                "/api/v1/webhooks/stripe-connect",
                content=b'{"test": true}',
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "processing_error"

    @patch(f"{WEBHOOK_MODULE}.StripeConnectService")
    @patch(f"{WEBHOOK_MODULE}.crud")
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_events_marked_failed_on_processing_error(
        self, mock_settings, mock_crud, mock_service_cls, webhook_client
    ):
        """Events are marked as failed when processing errors occur."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test"
        event = _make_stripe_event(
            event_type="account.updated",
            data_object={"id": "acct_test123"},
        )

        mock_crud.webhook_event.is_already_processed.return_value = False
        mock_webhook_event = MagicMock()
        mock_webhook_event.id = "whe_mark_fail"
        mock_crud.webhook_event.upsert_event.return_value = mock_webhook_event

        mock_service = MagicMock()
        mock_service.handle_account_updated = AsyncMock(
            side_effect=ValueError("Invalid data")
        )
        mock_service_cls.return_value = mock_service

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = webhook_client.post(
                "/api/v1/webhooks/stripe-connect",
                content=b'{"test": true}',
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

        assert response.status_code == 200
        # Verify mark_failed was called with the right event_id and error
        mock_crud.webhook_event.mark_failed.assert_called_once()
        call_args = mock_crud.webhook_event.mark_failed.call_args
        assert call_args[1]["event_id"] == "whe_mark_fail"
        assert "Invalid data" in call_args[1]["error"]


# =========================================================================== #
# 6. Direct Helper Function Tests
# =========================================================================== #


class TestHandleAccountDeauthorized:
    """Tests for the _handle_account_deauthorized helper."""

    def test_marks_org_as_inactive(self):
        """Deauthorization sets is_active=False and clears payment flags."""
        from app.api.v1.endpoints.connect_webhooks import _handle_account_deauthorized

        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        account_data = {"id": "acct_test123"}

        run_async(_handle_account_deauthorized(account_data, mock_db))

        assert org_settings.is_active is False
        assert org_settings.charges_enabled is False
        assert org_settings.payouts_enabled is False
        assert org_settings.verified_at is None
        assert org_settings.deauthorized_at is not None
        mock_db.commit.assert_called_once()

    def test_no_account_id_does_nothing(self):
        """Event without account ID does nothing."""
        from app.api.v1.endpoints.connect_webhooks import _handle_account_deauthorized

        mock_db = MagicMock()

        run_async(_handle_account_deauthorized({}, mock_db))

        mock_db.query.assert_not_called()
        mock_db.commit.assert_not_called()

    def test_unknown_account_does_nothing(self):
        """Event for unknown account does nothing."""
        from app.api.v1.endpoints.connect_webhooks import _handle_account_deauthorized

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        run_async(_handle_account_deauthorized({"id": "acct_unknown"}, mock_db))

        mock_db.commit.assert_not_called()

    def test_sets_deauthorized_at_timestamp(self):
        """Deauthorization records the timestamp of deauthorization."""
        from app.api.v1.endpoints.connect_webhooks import _handle_account_deauthorized

        org_settings = _make_org_settings(deauthorized_at=None)
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        before = datetime.now(timezone.utc)
        run_async(_handle_account_deauthorized({"id": "acct_test123"}, mock_db))
        after = datetime.now(timezone.utc)

        assert org_settings.deauthorized_at is not None
        assert before <= org_settings.deauthorized_at <= after


class TestHandleCapabilityUpdated:
    """Tests for the _handle_capability_updated helper."""

    @patch(f"{WEBHOOK_MODULE}.stripe.Account.retrieve")
    def test_inactive_capability_updates_account_status(self, mock_retrieve):
        """Inactive capability triggers re-fetch and status update."""
        from app.api.v1.endpoints.connect_webhooks import _handle_capability_updated

        mock_account = MagicMock()
        mock_account.charges_enabled = False
        mock_account.payouts_enabled = True
        mock_retrieve.return_value = mock_account

        org_settings = _make_org_settings(charges_enabled=True, payouts_enabled=True)
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        capability_data = {
            "id": "card_payments",
            "account": "acct_test123",
            "status": "inactive",
        }

        run_async(_handle_capability_updated(capability_data, mock_db))

        mock_retrieve.assert_called_once_with("acct_test123")
        assert org_settings.charges_enabled is False
        assert org_settings.payouts_enabled is True
        mock_db.commit.assert_called_once()

    @patch(f"{WEBHOOK_MODULE}.stripe.Account.retrieve")
    def test_unrequested_capability_also_triggers_update(self, mock_retrieve):
        """Unrequested capability status also triggers re-fetch."""
        from app.api.v1.endpoints.connect_webhooks import _handle_capability_updated

        mock_account = MagicMock()
        mock_account.charges_enabled = True
        mock_account.payouts_enabled = False
        mock_retrieve.return_value = mock_account

        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        capability_data = {
            "id": "transfers",
            "account": "acct_test123",
            "status": "unrequested",
        }

        run_async(_handle_capability_updated(capability_data, mock_db))

        mock_retrieve.assert_called_once_with("acct_test123")
        assert org_settings.payouts_enabled is False

    def test_active_capability_does_not_refetch(self):
        """Active capability does not trigger re-fetch or DB update."""
        from app.api.v1.endpoints.connect_webhooks import _handle_capability_updated

        mock_db = MagicMock()

        capability_data = {
            "id": "card_payments",
            "account": "acct_test123",
            "status": "active",
        }

        run_async(_handle_capability_updated(capability_data, mock_db))

        # No DB query for org settings since status is active
        mock_db.query.assert_not_called()

    def test_no_account_id_returns_early(self):
        """Capability event without account ID returns early."""
        from app.api.v1.endpoints.connect_webhooks import _handle_capability_updated

        mock_db = MagicMock()

        capability_data = {"id": "card_payments", "status": "inactive"}

        run_async(_handle_capability_updated(capability_data, mock_db))

        mock_db.query.assert_not_called()

    @patch(f"{WEBHOOK_MODULE}.stripe.Account.retrieve")
    def test_unknown_account_for_capability(self, mock_retrieve):
        """Capability event for unknown account does not crash."""
        from app.api.v1.endpoints.connect_webhooks import _handle_capability_updated

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        capability_data = {
            "id": "card_payments",
            "account": "acct_unknown",
            "status": "inactive",
        }

        run_async(_handle_capability_updated(capability_data, mock_db))

        # Should not call stripe.Account.retrieve since no org_settings found
        mock_retrieve.assert_not_called()

    @patch(f"{WEBHOOK_MODULE}.stripe.Account.retrieve")
    def test_stripe_error_during_capability_does_not_crash(self, mock_retrieve):
        """Stripe API error during capability update is handled gracefully."""
        from app.api.v1.endpoints.connect_webhooks import _handle_capability_updated

        mock_retrieve.side_effect = stripe.error.StripeError(
            message="API temporarily unavailable"
        )

        org_settings = _make_org_settings()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = org_settings

        capability_data = {
            "id": "card_payments",
            "account": "acct_test123",
            "status": "inactive",
        }

        # Should not raise
        run_async(_handle_capability_updated(capability_data, mock_db))

        # Should not commit since the retrieve failed
        mock_db.commit.assert_not_called()


# =========================================================================== #
# 7. Webhook Event Lifecycle
# =========================================================================== #


class TestWebhookEventLifecycle:
    """Tests for the webhook event storage and status lifecycle."""

    @patch(f"{WEBHOOK_MODULE}.crud")
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_event_stored_before_processing(
        self, mock_settings, mock_crud, webhook_client
    ):
        """Webhook event is stored and marked as processing before handlers run."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test"
        event = _make_stripe_event(
            event_type="some.unknown.event", data_object={"id": "test"}
        )

        mock_crud.webhook_event.is_already_processed.return_value = False
        mock_webhook_event = MagicMock()
        mock_webhook_event.id = "whe_lifecycle"
        mock_crud.webhook_event.upsert_event.return_value = mock_webhook_event

        with patch("stripe.Webhook.construct_event", return_value=event):
            response = webhook_client.post(
                "/api/v1/webhooks/stripe-connect",
                content=b'{"test": true}',
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

        assert response.status_code == 200
        # Verify lifecycle: is_already_processed -> upsert_event -> mark_processing -> mark_processed
        mock_crud.webhook_event.is_already_processed.assert_called_once()
        mock_crud.webhook_event.upsert_event.assert_called_once()
        mock_crud.webhook_event.mark_processing.assert_called_once()
        mark_processing_kwargs = mock_crud.webhook_event.mark_processing.call_args[1]
        assert mark_processing_kwargs["event_id"] == "whe_lifecycle"
        mock_crud.webhook_event.mark_processed.assert_called_once()

    @patch(f"{WEBHOOK_MODULE}.StripeConnectService")
    @patch(f"{WEBHOOK_MODULE}.crud")
    @patch(f"{WEBHOOK_MODULE}.settings")
    def test_successful_processing_marks_event_processed(
        self, mock_settings, mock_crud, mock_service_cls, webhook_client
    ):
        """Successful event processing marks the event as processed."""
        mock_settings.STRIPE_CONNECT_WEBHOOK_SECRET = "whsec_test"
        event = _make_stripe_event(
            event_type="account.updated",
            data_object={"id": "acct_test123"},
        )

        mock_crud.webhook_event.is_already_processed.return_value = False
        mock_webhook_event = MagicMock()
        mock_webhook_event.id = "whe_success"
        mock_crud.webhook_event.upsert_event.return_value = mock_webhook_event

        mock_service = MagicMock()
        mock_service.handle_account_updated = AsyncMock()
        mock_service_cls.return_value = mock_service

        with patch(
            f"{WEBHOOK_MODULE}._send_account_status_emails", new_callable=AsyncMock
        ):
            with patch("stripe.Webhook.construct_event", return_value=event):
                response = webhook_client.post(
                    "/api/v1/webhooks/stripe-connect",
                    content=b'{"test": true}',
                    headers={
                        "Content-Type": "application/json",
                        "Stripe-Signature": "t=123,v1=abc",
                    },
                )

        assert response.status_code == 200
        mock_crud.webhook_event.mark_processed.assert_called_once()
        mock_crud.webhook_event.mark_failed.assert_not_called()
