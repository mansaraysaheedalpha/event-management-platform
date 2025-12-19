"""Create payment tables for payment provider integration

Revision ID: p001_payment_tables
Revises: a1b2c3d4e5f6
Create Date: 2025-12-18 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "p001_payment_tables"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create payment_providers table
    op.create_table(
        "payment_providers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("supported_currencies", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False),
        sa.Column("supported_countries", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False),
        sa.Column("supported_features", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_payment_providers_code"),
    )
    op.create_index("idx_payment_providers_code", "payment_providers", ["code"])
    op.create_index("idx_payment_providers_active", "payment_providers", ["is_active"], postgresql_where=sa.text("is_active = true"))

    # Create organization_payment_settings table
    op.create_table(
        "organization_payment_settings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("provider_id", sa.String(), nullable=False),
        sa.Column("connected_account_id", sa.String(255), nullable=True),
        sa.Column("payout_schedule", sa.String(50), server_default="automatic", nullable=True),
        sa.Column("payout_currency", sa.String(3), server_default="USD", nullable=True),
        sa.Column("platform_fee_percent", sa.Numeric(5, 4), server_default="0.0000", nullable=True),
        sa.Column("platform_fee_fixed", sa.Integer(), server_default="0", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["provider_id"], ["payment_providers.id"]),
        sa.UniqueConstraint("organization_id", "provider_id", name="uq_org_provider"),
    )
    op.create_index("idx_org_payment_org", "organization_payment_settings", ["organization_id"])
    op.create_index("idx_org_payment_provider", "organization_payment_settings", ["provider_id"])

    # Create ticket_types table
    op.create_table(
        "ticket_types",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("quantity_total", sa.Integer(), nullable=True),
        sa.Column("quantity_sold", sa.Integer(), server_default="0", nullable=False),
        sa.Column("min_per_order", sa.Integer(), server_default="1", nullable=False),
        sa.Column("max_per_order", sa.Integer(), server_default="10", nullable=False),
        sa.Column("sales_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sales_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_ticket_types_event", "ticket_types", ["event_id"])
    op.create_index("idx_ticket_types_active", "ticket_types", ["is_active"])

    # Create promo_codes table
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("discount_type", sa.String(20), nullable=False),  # 'percentage' or 'fixed'
        sa.Column("discount_value", sa.Integer(), nullable=False),  # percentage (0-100) or fixed amount in cents
        sa.Column("currency", sa.String(3), server_default="USD", nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("times_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("min_order_amount", sa.Integer(), nullable=True),
        sa.Column("max_discount_amount", sa.Integer(), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("organization_id", "code", name="uq_org_promo_code"),
    )
    op.create_index("idx_promo_codes_org", "promo_codes", ["organization_id"])
    op.create_index("idx_promo_codes_code", "promo_codes", ["code"])
    op.create_index("idx_promo_codes_event", "promo_codes", ["event_id"])

    # Create orders table
    op.create_table(
        "orders",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("order_number", sa.String(50), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("guest_email", sa.String(255), nullable=True),
        sa.Column("guest_first_name", sa.String(100), nullable=True),
        sa.Column("guest_last_name", sa.String(100), nullable=True),
        sa.Column("guest_phone", sa.String(50), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("subtotal", sa.Integer(), nullable=False),
        sa.Column("discount_amount", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tax_amount", sa.Integer(), server_default="0", nullable=False),
        sa.Column("platform_fee", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_amount", sa.Integer(), nullable=False),
        sa.Column("promo_code_id", sa.String(), nullable=True),
        sa.Column("payment_provider", sa.String(50), nullable=True),
        sa.Column("payment_intent_id", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("order_metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["promo_code_id"], ["promo_codes.id"]),
        sa.UniqueConstraint("order_number", name="uq_orders_order_number"),
    )
    op.create_index("idx_orders_event", "orders", ["event_id"])
    op.create_index("idx_orders_user", "orders", ["user_id"], postgresql_where=sa.text("user_id IS NOT NULL"))
    op.create_index("idx_orders_status", "orders", ["status"])
    op.create_index("idx_orders_payment_intent", "orders", ["payment_intent_id"], postgresql_where=sa.text("payment_intent_id IS NOT NULL"))
    op.create_index("idx_orders_number", "orders", ["order_number"])
    op.create_index("idx_orders_created", "orders", ["created_at"])
    op.create_index("idx_orders_expires", "orders", ["expires_at"], postgresql_where=sa.text("status = 'pending'"))
    op.create_index("idx_orders_organization", "orders", ["organization_id"])

    # Create order_items table
    op.create_table(
        "order_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("ticket_type_id", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Integer(), nullable=False),
        sa.Column("ticket_type_name", sa.String(255), nullable=False),
        sa.Column("ticket_type_description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_type_id"], ["ticket_types.id"]),
        sa.CheckConstraint("quantity > 0", name="check_order_items_quantity_positive"),
    )
    op.create_index("idx_order_items_order", "order_items", ["order_id"])
    op.create_index("idx_order_items_ticket_type", "order_items", ["ticket_type_id"])

    # Create payments table
    op.create_table(
        "payments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("provider_code", sa.String(50), nullable=False),
        sa.Column("provider_payment_id", sa.String(255), nullable=False),
        sa.Column("provider_intent_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("amount_refunded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("provider_fee", sa.Integer(), server_default="0", nullable=False),
        sa.Column("net_amount", sa.Integer(), nullable=False),
        sa.Column("payment_method_type", sa.String(50), nullable=True),
        sa.Column("payment_method_details", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=True),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
    )
    op.create_index("idx_payments_order", "payments", ["order_id"])
    op.create_index("idx_payments_org", "payments", ["organization_id"])
    op.create_index("idx_payments_provider_id", "payments", ["provider_payment_id"])
    op.create_index("idx_payments_status", "payments", ["status"])
    op.create_index("idx_payments_created", "payments", ["created_at"])
    op.create_index("idx_payments_idempotency", "payments", ["idempotency_key"], unique=True, postgresql_where=sa.text("idempotency_key IS NOT NULL"))

    # Create refunds table
    op.create_table(
        "refunds",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("payment_id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("initiated_by_user_id", sa.String(), nullable=True),
        sa.Column("provider_code", sa.String(50), nullable=False),
        sa.Column("provider_refund_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("reason_details", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("failure_code", sa.String(100), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
    )
    op.create_index("idx_refunds_payment", "refunds", ["payment_id"])
    op.create_index("idx_refunds_order", "refunds", ["order_id"])
    op.create_index("idx_refunds_org", "refunds", ["organization_id"])
    op.create_index("idx_refunds_status", "refunds", ["status"])
    op.create_index("idx_refunds_idempotency", "refunds", ["idempotency_key"], unique=True, postgresql_where=sa.text("idempotency_key IS NOT NULL"))

    # Create payment_webhook_events table
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("provider_code", sa.String(50), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("provider_event_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("signature_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("related_payment_id", sa.String(), nullable=True),
        sa.Column("related_order_id", sa.String(), nullable=True),
        sa.Column("related_refund_id", sa.String(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["related_payment_id"], ["payments.id"]),
        sa.ForeignKeyConstraint(["related_order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["related_refund_id"], ["refunds.id"]),
    )
    op.create_index("idx_webhook_provider_event", "payment_webhook_events", ["provider_code", "provider_event_id"], unique=True)
    op.create_index("idx_webhook_status", "payment_webhook_events", ["status"])
    op.create_index("idx_webhook_retry", "payment_webhook_events", ["next_retry_at"], postgresql_where=sa.text("status = 'failed' AND retry_count < 5"))
    op.create_index("idx_webhook_event_type", "payment_webhook_events", ["provider_event_type"])
    op.create_index("idx_webhook_received", "payment_webhook_events", ["received_at"])

    # Create payment_audit_log table
    op.create_table(
        "payment_audit_log",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("actor_type", sa.String(50), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("actor_ip", sa.String(45), nullable=True),
        sa.Column("actor_user_agent", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("previous_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("change_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column("event_id", sa.String(), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_entity", "payment_audit_log", ["entity_type", "entity_id"])
    op.create_index("idx_audit_action", "payment_audit_log", ["action"])
    op.create_index("idx_audit_actor", "payment_audit_log", ["actor_type", "actor_id"])
    op.create_index("idx_audit_org", "payment_audit_log", ["organization_id"])
    op.create_index("idx_audit_created", "payment_audit_log", ["created_at"])
    op.create_index("idx_audit_request", "payment_audit_log", ["request_id"], postgresql_where=sa.text("request_id IS NOT NULL"))

    # Insert default Stripe provider
    op.execute("""
        INSERT INTO payment_providers (id, code, name, is_active, is_default, supported_currencies, supported_countries, supported_features, config)
        VALUES (
            'pp_stripe_default',
            'stripe',
            'Stripe',
            true,
            true,
            ARRAY['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF', 'DKK', 'NOK', 'SEK', 'SGD', 'HKD', 'NZD'],
            ARRAY['US', 'CA', 'GB', 'AU', 'NZ', 'SG', 'HK', 'JP', 'DE', 'FR', 'IT', 'ES', 'NL', 'BE', 'AT', 'CH', 'IE', 'DK', 'NO', 'SE', 'FI'],
            '{"refunds": true, "partial_refunds": true, "subscriptions": true, "saved_payment_methods": true, "3d_secure": true, "webhooks": true, "connect_marketplace": true}',
            '{"api_version": "2023-10-16", "statement_descriptor": "EVENT PLATFORM"}'
        )
    """)


def downgrade() -> None:
    op.drop_index("idx_audit_request", table_name="payment_audit_log")
    op.drop_index("idx_audit_created", table_name="payment_audit_log")
    op.drop_index("idx_audit_org", table_name="payment_audit_log")
    op.drop_index("idx_audit_actor", table_name="payment_audit_log")
    op.drop_index("idx_audit_action", table_name="payment_audit_log")
    op.drop_index("idx_audit_entity", table_name="payment_audit_log")
    op.drop_table("payment_audit_log")

    op.drop_index("idx_webhook_received", table_name="payment_webhook_events")
    op.drop_index("idx_webhook_event_type", table_name="payment_webhook_events")
    op.drop_index("idx_webhook_retry", table_name="payment_webhook_events")
    op.drop_index("idx_webhook_status", table_name="payment_webhook_events")
    op.drop_index("idx_webhook_provider_event", table_name="payment_webhook_events")
    op.drop_table("payment_webhook_events")

    op.drop_index("idx_refunds_idempotency", table_name="refunds")
    op.drop_index("idx_refunds_status", table_name="refunds")
    op.drop_index("idx_refunds_org", table_name="refunds")
    op.drop_index("idx_refunds_order", table_name="refunds")
    op.drop_index("idx_refunds_payment", table_name="refunds")
    op.drop_table("refunds")

    op.drop_index("idx_payments_idempotency", table_name="payments")
    op.drop_index("idx_payments_created", table_name="payments")
    op.drop_index("idx_payments_status", table_name="payments")
    op.drop_index("idx_payments_provider_id", table_name="payments")
    op.drop_index("idx_payments_org", table_name="payments")
    op.drop_index("idx_payments_order", table_name="payments")
    op.drop_table("payments")

    op.drop_index("idx_order_items_ticket_type", table_name="order_items")
    op.drop_index("idx_order_items_order", table_name="order_items")
    op.drop_table("order_items")

    op.drop_index("idx_orders_organization", table_name="orders")
    op.drop_index("idx_orders_expires", table_name="orders")
    op.drop_index("idx_orders_created", table_name="orders")
    op.drop_index("idx_orders_number", table_name="orders")
    op.drop_index("idx_orders_payment_intent", table_name="orders")
    op.drop_index("idx_orders_status", table_name="orders")
    op.drop_index("idx_orders_user", table_name="orders")
    op.drop_index("idx_orders_event", table_name="orders")
    op.drop_table("orders")

    op.drop_index("idx_promo_codes_event", table_name="promo_codes")
    op.drop_index("idx_promo_codes_code", table_name="promo_codes")
    op.drop_index("idx_promo_codes_org", table_name="promo_codes")
    op.drop_table("promo_codes")

    op.drop_index("idx_ticket_types_active", table_name="ticket_types")
    op.drop_index("idx_ticket_types_event", table_name="ticket_types")
    op.drop_table("ticket_types")

    op.drop_index("idx_org_payment_provider", table_name="organization_payment_settings")
    op.drop_index("idx_org_payment_org", table_name="organization_payment_settings")
    op.drop_table("organization_payment_settings")

    op.drop_index("idx_payment_providers_active", table_name="payment_providers")
    op.drop_index("idx_payment_providers_code", table_name="payment_providers")
    op.drop_table("payment_providers")
