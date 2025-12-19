# Payment Provider Interface - Backend Requirements

> **Document Version:** 1.0
> **Last Updated:** December 2025
> **Status:** Implementation Ready
> **Security Level:** PCI-DSS Compliant Architecture

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Database Schema](#3-database-schema)
4. [Payment Provider Interface](#4-payment-provider-interface)
5. [Stripe Implementation](#5-stripe-implementation)
6. [API Endpoints](#6-api-endpoints)
7. [Webhook Handling](#7-webhook-handling)
8. [Security Requirements](#8-security-requirements)
9. [Error Handling](#9-error-handling)
10. [Audit & Compliance](#10-audit--compliance)
11. [Testing Requirements](#11-testing-requirements)

---

## 1. Executive Summary

### 1.1 Purpose

Build a payment provider abstraction layer that:
- Supports multiple payment providers (Stripe first, then Paystack, Flutterwave, etc.)
- Handles ticket purchases for events
- Manages refunds and cancellations
- Maintains complete audit trails
- Follows PCI-DSS compliance requirements

### 1.2 Design Principles

| Principle | Description |
|-----------|-------------|
| **Provider Agnostic** | Core payment logic is decoupled from specific providers |
| **Idempotent** | All payment operations are safely retriable |
| **Auditable** | Every financial operation is logged with full context |
| **Secure by Default** | No sensitive data stored, all secrets in environment |
| **Fail-Safe** | Graceful degradation, no orphaned payments |
| **Eventually Consistent** | Webhook-driven status updates with reconciliation |

### 1.3 Supported Operations

```
┌─────────────────────────────────────────────────────────────┐
│                    Payment Operations                        │
├─────────────────────────────────────────────────────────────┤
│  CREATE_PAYMENT_INTENT    → Initialize a payment session    │
│  CONFIRM_PAYMENT          → Finalize payment (webhook)      │
│  CANCEL_PAYMENT           → Cancel pending payment          │
│  REFUND_PAYMENT           → Full or partial refund          │
│  GET_PAYMENT_STATUS       → Query payment state             │
│  LIST_PAYMENTS            → Paginated payment history       │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ Checkout Page   │  │ Payment Form    │  │ Order Summary   │         │
│  │ (Server Comp)   │  │ (Stripe Elements│  │ (Server Comp)   │         │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘         │
└───────────┼─────────────────────┼─────────────────────┼─────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           BACKEND API                                    │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Payment Service Layer                          │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐  │   │
│  │  │ PaymentService │  │ RefundService  │  │ ReconciliationSvc  │  │   │
│  │  └───────┬────────┘  └───────┬────────┘  └─────────┬──────────┘  │   │
│  │          │                   │                     │              │   │
│  │          ▼                   ▼                     ▼              │   │
│  │  ┌────────────────────────────────────────────────────────────┐  │   │
│  │  │              PaymentProviderInterface                       │  │   │
│  │  │  ┌──────────────────────────────────────────────────────┐  │  │   │
│  │  │  │  + createPaymentIntent(order: Order): PaymentIntent  │  │  │   │
│  │  │  │  + confirmPayment(intentId: string): Payment         │  │  │   │
│  │  │  │  + cancelPayment(intentId: string): void             │  │  │   │
│  │  │  │  + refundPayment(paymentId: string, amt?): Refund    │  │  │   │
│  │  │  │  + getPaymentStatus(paymentId: string): Status       │  │  │   │
│  │  │  │  + verifyWebhookSignature(payload, sig): boolean     │  │  │   │
│  │  │  └──────────────────────────────────────────────────────┘  │  │   │
│  │  └───────────────────────────┬────────────────────────────────┘  │   │
│  └──────────────────────────────┼───────────────────────────────────┘   │
│                                 │                                        │
│         ┌───────────────────────┼───────────────────────┐               │
│         ▼                       ▼                       ▼               │
│  ┌──────────────┐       ┌──────────────┐       ┌──────────────┐        │
│  │StripeProvider│       │PaystackProv  │       │FlutterwavePr │        │
│  │(Implemented) │       │(Future)      │       │(Future)      │        │
│  └──────────────┘       └──────────────┘       └──────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
            │                                             ▲
            ▼                                             │
┌─────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SERVICES                                │
│  ┌──────────────┐       ┌──────────────┐       ┌──────────────┐        │
│  │ Stripe API   │──────▶│ Webhooks     │──────▶│ Event Queue  │        │
│  └──────────────┘       └──────────────┘       └──────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Payment Flow Sequence

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │     │  Backend │     │ Provider │     │  Stripe  │     │  Webhook │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │                │
     │ 1. Create Order│                │                │                │
     │───────────────▶│                │                │                │
     │                │                │                │                │
     │                │ 2. Create Payment Intent        │                │
     │                │───────────────▶│                │                │
     │                │                │ 3. Stripe API  │                │
     │                │                │───────────────▶│                │
     │                │                │                │                │
     │                │                │ 4. Intent + Client Secret       │
     │                │                │◀───────────────│                │
     │                │ 5. Return      │                │                │
     │                │◀───────────────│                │                │
     │ 6. Client Secret                │                │                │
     │◀───────────────│                │                │                │
     │                │                │                │                │
     │ 7. Confirm with Stripe.js       │                │                │
     │─────────────────────────────────────────────────▶│                │
     │                │                │                │                │
     │ 8. Payment Complete             │                │                │
     │◀─────────────────────────────────────────────────│                │
     │                │                │                │                │
     │                │                │                │ 9. Webhook Event
     │                │                │                │───────────────▶│
     │                │                │                │                │
     │                │ 10. Process Webhook             │                │
     │                │◀─────────────────────────────────────────────────│
     │                │                │                │                │
     │                │ 11. Update Order Status         │                │
     │                │────────────────┼────────────────┼────────────────│
     │                │                │                │                │
     │ 12. Real-time Update (WebSocket)│                │                │
     │◀───────────────│                │                │                │
     │                │                │                │                │
```

### 2.3 Provider Selection Logic

```typescript
// Provider selection based on configuration and context
interface ProviderSelectionContext {
  currency: string;
  country: string;
  amount: number;
  organizationId: string;
}

// Provider is selected based on:
// 1. Organization's configured provider (if set)
// 2. Currency/region mapping (e.g., NGN → Paystack, USD → Stripe)
// 3. Fallback to default provider

// Example mapping (configured in environment/database):
const PROVIDER_ROUTING = {
  currencies: {
    'USD': 'stripe',
    'EUR': 'stripe',
    'GBP': 'stripe',
    'NGN': 'paystack',  // Future
    'GHS': 'paystack',  // Future
    'KES': 'flutterwave', // Future
  },
  default: 'stripe'
};
```

---

## 3. Database Schema

### 3.1 Core Tables

#### 3.1.1 `payment_providers` Table

Stores available payment provider configurations.

```sql
CREATE TABLE payment_providers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Provider identification
    code            VARCHAR(50) UNIQUE NOT NULL,  -- 'stripe', 'paystack', etc.
    name            VARCHAR(100) NOT NULL,

    -- Status
    is_active       BOOLEAN DEFAULT true,
    is_default      BOOLEAN DEFAULT false,

    -- Supported features (JSON for flexibility)
    supported_currencies    TEXT[] NOT NULL DEFAULT '{}',
    supported_countries     TEXT[] NOT NULL DEFAULT '{}',
    supported_features      JSONB DEFAULT '{}',
    -- Example: {"refunds": true, "partial_refunds": true, "subscriptions": false}

    -- Configuration (non-sensitive only)
    config          JSONB DEFAULT '{}',
    -- Example: {"webhook_api_version": "2023-10-16", "statement_descriptor": "GLOBALCONNECT"}

    -- Metadata
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_payment_providers_code ON payment_providers(code);
CREATE INDEX idx_payment_providers_active ON payment_providers(is_active) WHERE is_active = true;

-- Ensure only one default provider
CREATE UNIQUE INDEX idx_payment_providers_default ON payment_providers(is_default) WHERE is_default = true;
```

#### 3.1.2 `organization_payment_settings` Table

Per-organization payment configuration.

```sql
CREATE TABLE organization_payment_settings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Provider configuration
    provider_id         UUID NOT NULL REFERENCES payment_providers(id),

    -- Connected account (for marketplace model)
    -- NEVER store API keys here - use secure vault/environment
    connected_account_id    VARCHAR(255),  -- e.g., Stripe Connect account ID

    -- Payout settings
    payout_schedule     VARCHAR(50) DEFAULT 'automatic', -- 'automatic', 'manual', 'weekly', 'monthly'
    payout_currency     VARCHAR(3) DEFAULT 'USD',

    -- Fee configuration
    platform_fee_percent    DECIMAL(5,4) DEFAULT 0.0000,  -- e.g., 0.0250 = 2.5%
    platform_fee_fixed      INTEGER DEFAULT 0,  -- in smallest currency unit (cents)

    -- Status
    is_active           BOOLEAN DEFAULT true,
    verified_at         TIMESTAMP WITH TIME ZONE,

    -- Metadata
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT unique_org_provider UNIQUE (organization_id, provider_id)
);

-- Indexes
CREATE INDEX idx_org_payment_org ON organization_payment_settings(organization_id);
CREATE INDEX idx_org_payment_provider ON organization_payment_settings(provider_id);
```

#### 3.1.3 `orders` Table

Represents a purchase intent (cart checkout).

```sql
CREATE TABLE orders (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Reference
    order_number        VARCHAR(50) UNIQUE NOT NULL,  -- Human-readable: ORD-2024-XXXXX

    -- Relationships
    event_id            UUID NOT NULL REFERENCES events(id),
    organization_id     UUID NOT NULL REFERENCES organizations(id),
    user_id             UUID REFERENCES users(id),  -- NULL for guest checkout

    -- Guest information (when user_id is NULL)
    guest_email         VARCHAR(255),
    guest_first_name    VARCHAR(100),
    guest_last_name     VARCHAR(100),
    guest_phone         VARCHAR(50),

    -- Order status
    status              VARCHAR(50) NOT NULL DEFAULT 'pending',
    -- Values: 'pending', 'processing', 'completed', 'cancelled', 'refunded', 'partially_refunded', 'expired'

    -- Financial
    currency            VARCHAR(3) NOT NULL,  -- ISO 4217: USD, EUR, NGN, etc.
    subtotal            INTEGER NOT NULL,     -- in smallest currency unit (cents)
    discount_amount     INTEGER DEFAULT 0,
    tax_amount          INTEGER DEFAULT 0,
    platform_fee        INTEGER DEFAULT 0,
    total_amount        INTEGER NOT NULL,

    -- Applied discounts
    promo_code_id       UUID REFERENCES promo_codes(id),

    -- Payment tracking
    payment_provider    VARCHAR(50),
    payment_intent_id   VARCHAR(255),  -- Provider's payment intent/session ID

    -- Timestamps
    expires_at          TIMESTAMP WITH TIME ZONE,  -- Order expiration (e.g., 30 min)
    completed_at        TIMESTAMP WITH TIME ZONE,
    cancelled_at        TIMESTAMP WITH TIME ZONE,

    -- Metadata
    metadata            JSONB DEFAULT '{}',
    ip_address          INET,
    user_agent          TEXT,

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_orders_event ON orders(event_id);
CREATE INDEX idx_orders_user ON orders(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_payment_intent ON orders(payment_intent_id) WHERE payment_intent_id IS NOT NULL;
CREATE INDEX idx_orders_number ON orders(order_number);
CREATE INDEX idx_orders_created ON orders(created_at);
CREATE INDEX idx_orders_expires ON orders(expires_at) WHERE status = 'pending';

-- Order number generation function
CREATE OR REPLACE FUNCTION generate_order_number()
RETURNS TRIGGER AS $$
BEGIN
    NEW.order_number := 'ORD-' || TO_CHAR(NOW(), 'YYYY') || '-' ||
                        UPPER(SUBSTRING(MD5(NEW.id::text) FROM 1 FOR 6));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_order_number
    BEFORE INSERT ON orders
    FOR EACH ROW
    EXECUTE FUNCTION generate_order_number();
```

#### 3.1.4 `order_items` Table

Individual line items in an order.

```sql
CREATE TABLE order_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id            UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,

    -- What was purchased
    ticket_type_id      UUID NOT NULL REFERENCES ticket_types(id),

    -- Quantity and pricing (snapshot at time of purchase)
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    unit_price          INTEGER NOT NULL,  -- Price per ticket in cents
    total_price         INTEGER NOT NULL,  -- quantity * unit_price

    -- Snapshot of ticket type at purchase time
    ticket_type_name    VARCHAR(255) NOT NULL,
    ticket_type_description TEXT,

    -- Metadata
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_ticket_type ON order_items(ticket_type_id);
```

#### 3.1.5 `payments` Table

Records of actual payment transactions.

```sql
CREATE TABLE payments (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationships
    order_id                UUID NOT NULL REFERENCES orders(id),
    organization_id         UUID NOT NULL REFERENCES organizations(id),

    -- Provider information
    provider_code           VARCHAR(50) NOT NULL,  -- 'stripe', 'paystack', etc.
    provider_payment_id     VARCHAR(255) NOT NULL, -- Provider's payment/charge ID
    provider_intent_id      VARCHAR(255),          -- Payment intent ID if applicable

    -- Payment details
    status                  VARCHAR(50) NOT NULL,
    -- Values: 'pending', 'processing', 'succeeded', 'failed', 'cancelled', 'refunded', 'partially_refunded'

    -- Financial
    currency                VARCHAR(3) NOT NULL,
    amount                  INTEGER NOT NULL,      -- Amount charged in cents
    amount_refunded         INTEGER DEFAULT 0,     -- Total refunded amount
    provider_fee            INTEGER DEFAULT 0,     -- Stripe/Paystack fee
    net_amount              INTEGER NOT NULL,      -- amount - provider_fee

    -- Payment method details (non-sensitive only)
    payment_method_type     VARCHAR(50),           -- 'card', 'bank_transfer', etc.
    payment_method_details  JSONB DEFAULT '{}',
    -- Example: {"brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2025}

    -- Failure information
    failure_code            VARCHAR(100),
    failure_message         TEXT,

    -- Idempotency
    idempotency_key         VARCHAR(255) UNIQUE,

    -- Risk assessment
    risk_score              INTEGER,               -- 0-100
    risk_level              VARCHAR(20),           -- 'normal', 'elevated', 'high'

    -- Timestamps
    processed_at            TIMESTAMP WITH TIME ZONE,

    -- Metadata from provider
    provider_metadata       JSONB DEFAULT '{}',

    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_payments_order ON payments(order_id);
CREATE INDEX idx_payments_org ON payments(organization_id);
CREATE INDEX idx_payments_provider_id ON payments(provider_payment_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_created ON payments(created_at);
CREATE UNIQUE INDEX idx_payments_idempotency ON payments(idempotency_key) WHERE idempotency_key IS NOT NULL;
```

#### 3.1.6 `refunds` Table

Records of refund transactions.

```sql
CREATE TABLE refunds (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationships
    payment_id              UUID NOT NULL REFERENCES payments(id),
    order_id                UUID NOT NULL REFERENCES orders(id),
    organization_id         UUID NOT NULL REFERENCES organizations(id),
    initiated_by_user_id    UUID REFERENCES users(id),  -- Admin who initiated

    -- Provider information
    provider_code           VARCHAR(50) NOT NULL,
    provider_refund_id      VARCHAR(255),  -- Provider's refund ID

    -- Refund details
    status                  VARCHAR(50) NOT NULL,
    -- Values: 'pending', 'processing', 'succeeded', 'failed', 'cancelled'

    reason                  VARCHAR(100) NOT NULL,
    -- Values: 'requested_by_customer', 'duplicate', 'fraudulent', 'event_cancelled', 'other'
    reason_details          TEXT,

    -- Financial
    currency                VARCHAR(3) NOT NULL,
    amount                  INTEGER NOT NULL,          -- Refund amount in cents

    -- Idempotency
    idempotency_key         VARCHAR(255) UNIQUE,

    -- Failure information
    failure_code            VARCHAR(100),
    failure_message         TEXT,

    -- Timestamps
    processed_at            TIMESTAMP WITH TIME ZONE,

    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_refunds_payment ON refunds(payment_id);
CREATE INDEX idx_refunds_order ON refunds(order_id);
CREATE INDEX idx_refunds_org ON refunds(organization_id);
CREATE INDEX idx_refunds_status ON refunds(status);
CREATE UNIQUE INDEX idx_refunds_idempotency ON refunds(idempotency_key) WHERE idempotency_key IS NOT NULL;
```

#### 3.1.7 `payment_webhook_events` Table

Stores all incoming webhook events for audit and replay.

```sql
CREATE TABLE payment_webhook_events (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Provider information
    provider_code           VARCHAR(50) NOT NULL,
    provider_event_id       VARCHAR(255) NOT NULL,  -- Provider's event ID
    provider_event_type     VARCHAR(100) NOT NULL,  -- e.g., 'payment_intent.succeeded'

    -- Processing status
    status                  VARCHAR(50) NOT NULL DEFAULT 'pending',
    -- Values: 'pending', 'processing', 'processed', 'failed', 'skipped'

    -- Payload (encrypted at rest if required)
    payload                 JSONB NOT NULL,

    -- Signature verification
    signature_verified      BOOLEAN NOT NULL DEFAULT false,

    -- Processing details
    processed_at            TIMESTAMP WITH TIME ZONE,
    processing_error        TEXT,
    retry_count             INTEGER DEFAULT 0,
    next_retry_at           TIMESTAMP WITH TIME ZONE,

    -- Related entities (populated during processing)
    related_payment_id      UUID REFERENCES payments(id),
    related_order_id        UUID REFERENCES orders(id),
    related_refund_id       UUID REFERENCES refunds(id),

    -- Request metadata
    received_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ip_address              INET,

    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX idx_webhook_provider_event ON payment_webhook_events(provider_code, provider_event_id);
CREATE INDEX idx_webhook_status ON payment_webhook_events(status);
CREATE INDEX idx_webhook_retry ON payment_webhook_events(next_retry_at) WHERE status = 'failed' AND retry_count < 5;
CREATE INDEX idx_webhook_event_type ON payment_webhook_events(provider_event_type);
CREATE INDEX idx_webhook_received ON payment_webhook_events(received_at);
```

#### 3.1.8 `payment_audit_log` Table

Immutable audit trail for all payment-related operations.

```sql
CREATE TABLE payment_audit_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- What happened
    action              VARCHAR(100) NOT NULL,
    -- Values: 'order.created', 'payment.initiated', 'payment.succeeded', 'payment.failed',
    --         'refund.initiated', 'refund.succeeded', 'refund.failed', 'webhook.received', etc.

    -- Who did it
    actor_type          VARCHAR(50) NOT NULL,  -- 'user', 'system', 'webhook', 'admin'
    actor_id            UUID,                   -- User ID if applicable
    actor_ip            INET,
    actor_user_agent    TEXT,

    -- What was affected
    entity_type         VARCHAR(50) NOT NULL,  -- 'order', 'payment', 'refund'
    entity_id           UUID NOT NULL,

    -- Change details
    previous_state      JSONB,
    new_state           JSONB,
    change_details      JSONB,  -- Specific fields that changed

    -- Context
    organization_id     UUID,
    event_id            UUID,
    request_id          VARCHAR(100),          -- Correlation ID for request tracing

    -- Immutable timestamp
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_audit_entity ON payment_audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_action ON payment_audit_log(action);
CREATE INDEX idx_audit_actor ON payment_audit_log(actor_type, actor_id);
CREATE INDEX idx_audit_org ON payment_audit_log(organization_id);
CREATE INDEX idx_audit_created ON payment_audit_log(created_at);
CREATE INDEX idx_audit_request ON payment_audit_log(request_id) WHERE request_id IS NOT NULL;

-- Prevent updates and deletes on audit log
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log entries cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prevent_audit_update
    BEFORE UPDATE ON payment_audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_modification();

CREATE TRIGGER prevent_audit_delete
    BEFORE DELETE ON payment_audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_modification();
```

### 3.2 Supporting Tables

#### 3.2.1 `ticket_types` Table (Enhanced)

```sql
-- Assuming ticket_types exists, these are the required fields:
ALTER TABLE ticket_types ADD COLUMN IF NOT EXISTS price INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ticket_types ADD COLUMN IF NOT EXISTS currency VARCHAR(3) NOT NULL DEFAULT 'USD';
ALTER TABLE ticket_types ADD COLUMN IF NOT EXISTS quantity_total INTEGER;  -- NULL = unlimited
ALTER TABLE ticket_types ADD COLUMN IF NOT EXISTS quantity_sold INTEGER DEFAULT 0;
ALTER TABLE ticket_types ADD COLUMN IF NOT EXISTS min_per_order INTEGER DEFAULT 1;
ALTER TABLE ticket_types ADD COLUMN IF NOT EXISTS max_per_order INTEGER DEFAULT 10;
ALTER TABLE ticket_types ADD COLUMN IF NOT EXISTS sales_start_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE ticket_types ADD COLUMN IF NOT EXISTS sales_end_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE ticket_types ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
ALTER TABLE ticket_types ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0;

-- Check constraint for quantity
ALTER TABLE ticket_types ADD CONSTRAINT check_quantity
    CHECK (quantity_sold <= quantity_total OR quantity_total IS NULL);
```

---

## 4. Payment Provider Interface

### 4.1 Interface Definition

```typescript
// types/payment-provider.ts

/**
 * Core interface that all payment providers must implement.
 * This abstraction allows swapping providers without changing business logic.
 */
interface PaymentProviderInterface {
  /**
   * Provider identification
   */
  readonly code: string;  // 'stripe', 'paystack', etc.
  readonly name: string;  // 'Stripe', 'Paystack', etc.

  /**
   * Initialize a payment intent/session for checkout
   * Returns a client-side token for secure payment form
   */
  createPaymentIntent(params: CreatePaymentIntentParams): Promise<PaymentIntentResult>;

  /**
   * Retrieve current status of a payment intent
   */
  getPaymentIntent(intentId: string): Promise<PaymentIntentStatus>;

  /**
   * Cancel a pending payment intent
   */
  cancelPaymentIntent(intentId: string): Promise<void>;

  /**
   * Process a refund for a completed payment
   */
  createRefund(params: CreateRefundParams): Promise<RefundResult>;

  /**
   * Get details of a specific payment
   */
  getPayment(paymentId: string): Promise<PaymentDetails>;

  /**
   * Verify webhook signature
   */
  verifyWebhookSignature(payload: string | Buffer, signature: string): boolean;

  /**
   * Parse webhook event into standardized format
   */
  parseWebhookEvent(payload: string | Buffer): WebhookEvent;

  /**
   * Check if provider supports a specific feature
   */
  supportsFeature(feature: PaymentFeature): boolean;

  /**
   * Health check for the provider
   */
  healthCheck(): Promise<HealthCheckResult>;
}

/**
 * Parameters for creating a payment intent
 */
interface CreatePaymentIntentParams {
  orderId: string;
  amount: number;           // In smallest currency unit (cents)
  currency: string;         // ISO 4217
  customerId?: string;      // Provider's customer ID if exists
  customerEmail: string;
  customerName: string;
  description: string;
  metadata: Record<string, string>;
  idempotencyKey: string;

  // For marketplace/platform model
  connectedAccountId?: string;
  platformFeeAmount?: number;

  // Payment method restrictions
  allowedPaymentMethods?: string[];  // ['card', 'bank_transfer']

  // Capture settings
  captureMethod?: 'automatic' | 'manual';

  // Return URLs
  successUrl?: string;
  cancelUrl?: string;
}

/**
 * Result of creating a payment intent
 */
interface PaymentIntentResult {
  intentId: string;
  clientSecret: string;     // For client-side confirmation
  status: PaymentIntentStatusEnum;
  expiresAt?: Date;
  providerMetadata?: Record<string, unknown>;
}

/**
 * Standardized payment intent status
 */
enum PaymentIntentStatusEnum {
  REQUIRES_PAYMENT_METHOD = 'requires_payment_method',
  REQUIRES_CONFIRMATION = 'requires_confirmation',
  REQUIRES_ACTION = 'requires_action',
  PROCESSING = 'processing',
  SUCCEEDED = 'succeeded',
  CANCELLED = 'cancelled',
  FAILED = 'failed',
}

/**
 * Parameters for creating a refund
 */
interface CreateRefundParams {
  paymentId: string;        // Provider's payment/charge ID
  amount?: number;          // Optional for partial refund (in cents)
  reason: RefundReason;
  idempotencyKey: string;
  metadata?: Record<string, string>;
}

enum RefundReason {
  REQUESTED_BY_CUSTOMER = 'requested_by_customer',
  DUPLICATE = 'duplicate',
  FRAUDULENT = 'fraudulent',
  EVENT_CANCELLED = 'event_cancelled',
  OTHER = 'other',
}

/**
 * Result of a refund operation
 */
interface RefundResult {
  refundId: string;
  status: RefundStatus;
  amount: number;
  currency: string;
  providerMetadata?: Record<string, unknown>;
}

enum RefundStatus {
  PENDING = 'pending',
  SUCCEEDED = 'succeeded',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

/**
 * Standardized webhook event
 */
interface WebhookEvent {
  eventId: string;
  eventType: WebhookEventType;
  data: {
    paymentIntentId?: string;
    paymentId?: string;
    refundId?: string;
    status: string;
    amount?: number;
    currency?: string;
    metadata?: Record<string, string>;
    failureCode?: string;
    failureMessage?: string;
  };
  createdAt: Date;
  rawPayload: unknown;
}

enum WebhookEventType {
  PAYMENT_INTENT_CREATED = 'payment_intent.created',
  PAYMENT_INTENT_SUCCEEDED = 'payment_intent.succeeded',
  PAYMENT_INTENT_FAILED = 'payment_intent.failed',
  PAYMENT_INTENT_CANCELLED = 'payment_intent.cancelled',
  CHARGE_SUCCEEDED = 'charge.succeeded',
  CHARGE_FAILED = 'charge.failed',
  CHARGE_REFUNDED = 'charge.refunded',
  REFUND_CREATED = 'refund.created',
  REFUND_SUCCEEDED = 'refund.succeeded',
  REFUND_FAILED = 'refund.failed',
  UNKNOWN = 'unknown',
}

/**
 * Available payment features
 */
enum PaymentFeature {
  REFUNDS = 'refunds',
  PARTIAL_REFUNDS = 'partial_refunds',
  RECURRING = 'recurring',
  SAVED_PAYMENT_METHODS = 'saved_payment_methods',
  3D_SECURE = '3d_secure',
  BANK_TRANSFER = 'bank_transfer',
  MOBILE_MONEY = 'mobile_money',
  WEBHOOKS = 'webhooks',
  CONNECT_MARKETPLACE = 'connect_marketplace',
}

/**
 * Health check result
 */
interface HealthCheckResult {
  healthy: boolean;
  latencyMs: number;
  message?: string;
}
```

### 4.2 Provider Factory

```typescript
// services/payment/provider-factory.ts

interface PaymentProviderFactory {
  /**
   * Get provider by code
   */
  getProvider(code: string): PaymentProviderInterface;

  /**
   * Get provider for a specific order based on routing rules
   */
  getProviderForOrder(context: ProviderSelectionContext): PaymentProviderInterface;

  /**
   * Get the default provider
   */
  getDefaultProvider(): PaymentProviderInterface;

  /**
   * List all available providers
   */
  listAvailableProviders(): ProviderInfo[];

  /**
   * Check if a provider is available for a given context
   */
  isProviderAvailable(code: string, context: ProviderSelectionContext): boolean;
}

interface ProviderSelectionContext {
  currency: string;
  country?: string;
  amount: number;
  organizationId: string;
}

interface ProviderInfo {
  code: string;
  name: string;
  supportedCurrencies: string[];
  supportedCountries: string[];
  features: PaymentFeature[];
  isActive: boolean;
}
```

---

## 5. Stripe Implementation

### 5.1 Environment Variables Required

```bash
# Stripe API Keys (NEVER commit these)
STRIPE_SECRET_KEY=sk_live_xxxx           # Production secret key
STRIPE_PUBLISHABLE_KEY=pk_live_xxxx      # Production publishable key
STRIPE_WEBHOOK_SECRET=whsec_xxxx         # Webhook signing secret

# Test mode (use separate keys)
STRIPE_SECRET_KEY_TEST=sk_test_xxxx
STRIPE_PUBLISHABLE_KEY_TEST=pk_test_xxxx
STRIPE_WEBHOOK_SECRET_TEST=whsec_xxxx

# Configuration
STRIPE_API_VERSION=2023-10-16            # Lock API version
STRIPE_MAX_NETWORK_RETRIES=2             # Retry on network failures
PAYMENT_MODE=live                         # 'live' or 'test'
```

### 5.2 Stripe Provider Implementation Spec

```typescript
// services/payment/providers/stripe-provider.ts

/**
 * Stripe implementation of PaymentProviderInterface
 *
 * SECURITY NOTES:
 * - Never log full card details
 * - Always verify webhook signatures
 * - Use idempotency keys for all mutations
 * - Handle rate limiting gracefully
 */
class StripeProvider implements PaymentProviderInterface {
  readonly code = 'stripe';
  readonly name = 'Stripe';

  private readonly stripe: Stripe;
  private readonly webhookSecret: string;

  constructor(config: StripeConfig) {
    // Initialize with locked API version
    this.stripe = new Stripe(config.secretKey, {
      apiVersion: '2023-10-16',
      maxNetworkRetries: config.maxRetries ?? 2,
      typescript: true,
    });
    this.webhookSecret = config.webhookSecret;
  }

  async createPaymentIntent(params: CreatePaymentIntentParams): Promise<PaymentIntentResult> {
    // Implementation follows Stripe best practices:
    // 1. Use idempotency keys
    // 2. Set appropriate metadata for reconciliation
    // 3. Configure statement descriptor
    // 4. Handle Connect/marketplace if applicable
  }

  // ... other methods
}
```

### 5.3 Stripe Webhook Events to Handle

| Stripe Event | Action |
|--------------|--------|
| `payment_intent.succeeded` | Mark order as completed, create payment record, generate tickets |
| `payment_intent.payment_failed` | Mark order as failed, log failure reason |
| `payment_intent.canceled` | Mark order as cancelled |
| `payment_intent.processing` | Update order status to processing |
| `charge.refunded` | Update payment record, mark order as refunded |
| `charge.refund.updated` | Update refund status |
| `charge.dispute.created` | Flag payment, notify admin |
| `charge.dispute.closed` | Update dispute status |

---

## 6. API Endpoints

### 6.1 GraphQL Schema

```graphql
# ============================================
# Types
# ============================================

enum OrderStatus {
  PENDING
  PROCESSING
  COMPLETED
  CANCELLED
  REFUNDED
  PARTIALLY_REFUNDED
  EXPIRED
}

enum PaymentStatus {
  PENDING
  PROCESSING
  SUCCEEDED
  FAILED
  CANCELLED
  REFUNDED
  PARTIALLY_REFUNDED
}

enum RefundStatus {
  PENDING
  PROCESSING
  SUCCEEDED
  FAILED
  CANCELLED
}

enum RefundReason {
  REQUESTED_BY_CUSTOMER
  DUPLICATE
  FRAUDULENT
  EVENT_CANCELLED
  OTHER
}

type Money {
  amount: Int!            # In smallest currency unit (cents)
  currency: String!       # ISO 4217
  formatted: String!      # e.g., "$10.00"
}

type TicketType {
  id: ID!
  name: String!
  description: String
  price: Money!
  quantityTotal: Int      # null = unlimited
  quantityAvailable: Int
  minPerOrder: Int!
  maxPerOrder: Int!
  salesStartAt: DateTime
  salesEndAt: DateTime
  isOnSale: Boolean!
  sortOrder: Int!
}

type OrderItem {
  id: ID!
  ticketType: TicketType!
  ticketTypeName: String!       # Snapshot at purchase time
  quantity: Int!
  unitPrice: Money!
  totalPrice: Money!
}

type Order {
  id: ID!
  orderNumber: String!
  event: Event!
  status: OrderStatus!

  # Customer info
  customerEmail: String!
  customerName: String!
  isGuestOrder: Boolean!

  # Line items
  items: [OrderItem!]!

  # Financial
  subtotal: Money!
  discountAmount: Money
  taxAmount: Money
  totalAmount: Money!

  # Promo code if applied
  promoCode: PromoCode

  # Payment info (only for completed orders)
  payment: Payment

  # Timestamps
  expiresAt: DateTime
  completedAt: DateTime
  createdAt: DateTime!
}

type Payment {
  id: ID!
  status: PaymentStatus!
  amount: Money!
  amountRefunded: Money
  providerFee: Money
  netAmount: Money!

  # Payment method (sanitized - no full card numbers)
  paymentMethodType: String
  paymentMethodBrand: String    # visa, mastercard, etc.
  paymentMethodLast4: String

  processedAt: DateTime
  createdAt: DateTime!
}

type Refund {
  id: ID!
  status: RefundStatus!
  amount: Money!
  reason: RefundReason!
  reasonDetails: String
  processedAt: DateTime
  createdAt: DateTime!
}

type PaymentIntent {
  clientSecret: String!
  intentId: String!
  publishableKey: String!
  expiresAt: DateTime
}

type CheckoutSession {
  order: Order!
  paymentIntent: PaymentIntent!
}

# ============================================
# Inputs
# ============================================

input OrderItemInput {
  ticketTypeId: ID!
  quantity: Int!
}

input CreateOrderInput {
  eventId: ID!
  items: [OrderItemInput!]!
  promoCode: String

  # Guest checkout fields (required if not authenticated)
  guestEmail: String
  guestFirstName: String
  guestLastName: String
  guestPhone: String
}

input InitiateRefundInput {
  orderId: ID!
  amount: Int            # Optional - omit for full refund
  reason: RefundReason!
  reasonDetails: String
}

# ============================================
# Queries
# ============================================

type Query {
  # Get ticket types for an event (public)
  eventTicketTypes(eventId: ID!): [TicketType!]!

  # Get order by ID (authenticated - owner or admin only)
  order(id: ID!): Order

  # Get order by number (for confirmation pages)
  orderByNumber(orderNumber: String!): Order

  # List orders for current user
  myOrders(
    status: OrderStatus
    first: Int = 20
    after: String
  ): OrderConnection!

  # List orders for an event (organizer only)
  eventOrders(
    eventId: ID!
    status: OrderStatus
    search: String
    first: Int = 50
    after: String
  ): OrderConnection!

  # Get payment details (authenticated - owner or admin only)
  payment(id: ID!): Payment

  # Get refunds for an order (organizer only)
  orderRefunds(orderId: ID!): [Refund!]!
}

# ============================================
# Mutations
# ============================================

type Mutation {
  # Step 1: Create order and get payment intent
  # Returns checkout session with client secret for Stripe Elements
  createCheckoutSession(input: CreateOrderInput!): CheckoutSession!

  # Cancel a pending order (before payment)
  cancelOrder(orderId: ID!): Order!

  # Apply promo code to pending order
  applyPromoCode(orderId: ID!, promoCode: String!): Order!

  # Remove promo code from pending order
  removePromoCode(orderId: ID!): Order!

  # Initiate refund (organizer only)
  initiateRefund(input: InitiateRefundInput!): Refund!

  # Cancel pending refund (organizer only)
  cancelRefund(refundId: ID!): Refund!
}

# ============================================
# Subscriptions (Real-time updates)
# ============================================

type Subscription {
  # Subscribe to order status changes
  orderStatusChanged(orderId: ID!): Order!

  # Subscribe to payment status changes
  paymentStatusChanged(orderId: ID!): Payment!
}
```

### 6.2 REST Endpoints (Webhooks)

```yaml
# Webhook endpoints - these MUST be REST, not GraphQL

POST /api/webhooks/stripe
  Description: Stripe webhook endpoint
  Authentication: Stripe signature verification (no API key)
  Headers:
    - Stripe-Signature: t=...,v1=...,v0=...
  Body: Raw JSON (Stripe event payload)
  Response:
    - 200: Event received and processed
    - 400: Invalid payload or signature
    - 500: Processing error (Stripe will retry)

  Security:
    - Verify signature using STRIPE_WEBHOOK_SECRET
    - Process idempotently (check event ID hasn't been processed)
    - Return 200 quickly, process async if needed
    - Log all events to payment_webhook_events table

POST /api/webhooks/paystack
  Description: Paystack webhook endpoint (future)
  # Similar structure

# Internal endpoints (called by frontend only)

POST /api/v1/internal/payments/confirm-intent
  Description: Called after successful client-side payment
  Authentication: Session cookie + CSRF token
  Body:
    - orderId: string
    - paymentIntentId: string
  Response:
    - 200: { success: true, order: Order }
    - 400: { error: "INVALID_INTENT" }
    - 409: { error: "ORDER_ALREADY_COMPLETED" }
```

---

## 7. Webhook Handling

### 7.1 Webhook Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        WEBHOOK PROCESSING PIPELINE                       │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Receive    │────▶│   Validate   │────▶│    Store     │────▶│   Process    │
│   Webhook    │     │   Signature  │     │    Event     │     │    Async     │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │                    │
       ▼                    ▼                    ▼                    ▼
  Log IP, UA         Reject if           Insert into         Queue for
  & timestamp       signature fails    webhook_events       background
                    (return 400)       (return 200)          processing


┌─────────────────────────────────────────────────────────────────────────┐
│                        ASYNC PROCESSING FLOW                             │
└─────────────────────────────────────────────────────────────────────────┘

1. Dequeue Event
       │
       ▼
2. Check Idempotency
   ├── Already processed? → Skip
   └── New event? → Continue
       │
       ▼
3. Parse Event Type
   ├── payment_intent.succeeded → Handle Payment Success
   ├── payment_intent.failed → Handle Payment Failure
   ├── charge.refunded → Handle Refund
   └── Unknown → Log and skip
       │
       ▼
4. Update Database
   ├── Update order status
   ├── Create/update payment record
   ├── Generate tickets (if applicable)
   └── Write audit log
       │
       ▼
5. Trigger Side Effects
   ├── Send confirmation email
   ├── Emit WebSocket event
   └── Update analytics
       │
       ▼
6. Mark Event Processed
```

### 7.2 Idempotency Requirements

```typescript
/**
 * CRITICAL: All webhook handlers must be idempotent
 *
 * Rules:
 * 1. Check if event_id has been processed before doing anything
 * 2. Use database transactions for all state changes
 * 3. If processing fails partway, it must be safe to retry
 * 4. Store event_id in payment_webhook_events BEFORE processing
 * 5. Mark as processed AFTER all operations complete
 */

// Pseudo-code for idempotent webhook handling
async function handleWebhookEvent(event: WebhookEvent) {
  // 1. Check if already processed
  const existing = await db.paymentWebhookEvents.findByProviderId(event.id);
  if (existing?.status === 'processed') {
    return { status: 'skipped', reason: 'already_processed' };
  }

  // 2. Store event (or update if exists from failed previous attempt)
  await db.paymentWebhookEvents.upsert({
    providerEventId: event.id,
    status: 'processing',
    // ...
  });

  // 3. Process in transaction
  try {
    await db.transaction(async (tx) => {
      // All database operations here
      await processEvent(tx, event);
    });

    // 4. Mark as processed
    await db.paymentWebhookEvents.update(event.id, {
      status: 'processed',
      processedAt: new Date(),
    });
  } catch (error) {
    // 5. Mark as failed (will be retried)
    await db.paymentWebhookEvents.update(event.id, {
      status: 'failed',
      processingError: error.message,
      retryCount: (existing?.retryCount ?? 0) + 1,
      nextRetryAt: calculateNextRetry(existing?.retryCount ?? 0),
    });
    throw error;
  }
}
```

### 7.3 Retry Strategy

```typescript
/**
 * Exponential backoff with jitter for webhook retry
 */
function calculateNextRetry(retryCount: number): Date {
  const baseDelay = 60_000; // 1 minute
  const maxDelay = 86_400_000; // 24 hours
  const maxRetries = 5;

  if (retryCount >= maxRetries) {
    return null; // No more retries - requires manual intervention
  }

  // Exponential backoff: 1min, 5min, 25min, 2hr, 10hr
  const delay = Math.min(
    baseDelay * Math.pow(5, retryCount),
    maxDelay
  );

  // Add jitter (±10%)
  const jitter = delay * 0.1 * (Math.random() * 2 - 1);

  return new Date(Date.now() + delay + jitter);
}
```

---

## 8. Security Requirements

### 8.1 API Key Management

```yaml
CRITICAL REQUIREMENTS:

1. Secret Key Storage:
   - NEVER store in code, config files, or database
   - Use environment variables or secrets manager (AWS Secrets Manager, Vault)
   - Rotate keys periodically (at least annually)
   - Use separate keys for test and production

2. Publishable Key:
   - Can be exposed to frontend
   - Still avoid hardcoding - use environment variable
   - Different for test and production

3. Webhook Secret:
   - Used only server-side for signature verification
   - Treat with same security as secret key
   - Unique per webhook endpoint

4. Key Access Logging:
   - Log all API calls with key identifier (not full key)
   - Monitor for unusual patterns
   - Alert on failed authentication attempts
```

### 8.2 PCI-DSS Compliance Requirements

```yaml
GlobalConnect Payment Architecture - PCI-DSS Scope Reduction:

The system is designed to minimize PCI-DSS scope by:

1. NO CARD DATA STORAGE:
   - Never receive, transmit, or store raw card numbers
   - Use Stripe Elements for card input (iframe isolation)
   - Only store tokenized references (payment method IDs)

2. NO CARD DATA TRANSMISSION:
   - Card data goes directly to Stripe via their JS SDK
   - Backend only receives payment intent IDs
   - API never sees card numbers, CVVs, or expiry dates

3. TOKENIZATION:
   - All payment methods are represented by tokens
   - Tokens are provider-specific and non-reversible
   - Store only: last 4 digits, brand, expiry (for display)

4. STORED DATA (Safe to store):
   - Payment intent ID
   - Payment method type (card, bank_transfer)
   - Card brand (visa, mastercard)
   - Last 4 digits (for customer reference)
   - Expiry month/year (for card update reminders)

5. NEVER STORE:
   - Full card numbers (PAN)
   - CVV/CVC
   - PIN
   - Magnetic stripe data
   - Sensitive authentication data
```

### 8.3 Webhook Security

```yaml
Webhook Endpoint Security Checklist:

1. SIGNATURE VERIFICATION (MANDATORY):
   - Verify Stripe-Signature header on EVERY request
   - Reject requests with invalid/missing signatures
   - Use constant-time comparison for signatures

2. REPLAY PROTECTION:
   - Check event timestamp is within tolerance (5 min)
   - Store processed event IDs
   - Reject duplicate event IDs

3. IP WHITELISTING (OPTIONAL BUT RECOMMENDED):
   - Stripe webhook IPs: https://stripe.com/docs/ips#webhook-ip-addresses
   - Implement at infrastructure level (WAF, load balancer)

4. HTTPS ONLY:
   - Webhook endpoints MUST be HTTPS
   - Reject non-HTTPS in production

5. REQUEST VALIDATION:
   - Validate JSON structure
   - Validate event type is known
   - Validate required fields present

6. RATE LIMITING:
   - Implement rate limiting on webhook endpoint
   - Prevent DoS attacks
   - Return 429 with Retry-After header

7. TIMEOUT HANDLING:
   - Return 200 quickly (within 10 seconds)
   - Process asynchronously if needed
   - Stripe retries if no 2xx response
```

### 8.4 Idempotency Key Generation

```typescript
/**
 * Idempotency keys MUST be:
 * 1. Unique per operation
 * 2. Deterministic for retries
 * 3. Not guessable
 *
 * Format: {scope}_{entityId}_{action}_{timestamp}_{random}
 */

function generateIdempotencyKey(params: {
  scope: 'order' | 'refund';
  entityId: string;
  action: 'create' | 'confirm' | 'cancel' | 'refund';
}): string {
  const { scope, entityId, action } = params;
  const timestamp = Date.now();
  const random = crypto.randomBytes(8).toString('hex');

  return `${scope}_${entityId}_${action}_${timestamp}_${random}`;
}

// For retryable operations, use deterministic key:
function getDeterministicIdempotencyKey(params: {
  scope: 'order' | 'refund';
  entityId: string;
  action: 'create' | 'confirm' | 'cancel' | 'refund';
}): string {
  const { scope, entityId, action } = params;
  // This allows safe retries with same key
  return `${scope}_${entityId}_${action}`;
}
```

### 8.5 Input Validation

```typescript
/**
 * All payment-related inputs must be strictly validated
 */

// Amount validation
function validateAmount(amount: number, currency: string): void {
  if (!Number.isInteger(amount)) {
    throw new ValidationError('Amount must be an integer (cents)');
  }
  if (amount <= 0) {
    throw new ValidationError('Amount must be positive');
  }
  if (amount > 99999999) { // $999,999.99
    throw new ValidationError('Amount exceeds maximum');
  }

  // Currency-specific minimums
  const minimums: Record<string, number> = {
    'USD': 50,   // $0.50
    'EUR': 50,   // €0.50
    'GBP': 30,   // £0.30
    'NGN': 5000, // ₦50.00
  };

  if (amount < (minimums[currency] ?? 50)) {
    throw new ValidationError(`Amount below minimum for ${currency}`);
  }
}

// Currency validation
function validateCurrency(currency: string): void {
  const supported = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'NGN', 'GHS', 'KES'];
  if (!supported.includes(currency.toUpperCase())) {
    throw new ValidationError(`Currency ${currency} not supported`);
  }
}

// Email validation (for receipts)
function validateEmail(email: string): void {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    throw new ValidationError('Invalid email address');
  }
  if (email.length > 254) {
    throw new ValidationError('Email too long');
  }
}
```

### 8.6 Audit Logging Requirements

```yaml
Every payment operation MUST log:

1. WHAT happened:
   - Action type (create, confirm, refund, etc.)
   - Entity affected (order, payment, refund)
   - Previous state
   - New state

2. WHO did it:
   - Actor type (user, system, webhook, admin)
   - Actor ID (user ID if applicable)
   - IP address
   - User agent

3. WHEN it happened:
   - UTC timestamp
   - Request ID for correlation

4. CONTEXT:
   - Organization ID
   - Event ID
   - Related entity IDs

5. IMMUTABILITY:
   - Audit logs CANNOT be modified
   - Audit logs CANNOT be deleted
   - Use database triggers to enforce
```

---

## 9. Error Handling

### 9.1 Error Response Format

```typescript
/**
 * Standardized error response format
 */
interface PaymentError {
  code: PaymentErrorCode;
  message: string;           // User-friendly message
  details?: string;          // Technical details (dev only)
  retryable: boolean;
  suggestedAction?: string;  // What user should do
}

enum PaymentErrorCode {
  // Validation errors (400)
  INVALID_AMOUNT = 'INVALID_AMOUNT',
  INVALID_CURRENCY = 'INVALID_CURRENCY',
  INVALID_TICKET_TYPE = 'INVALID_TICKET_TYPE',
  QUANTITY_EXCEEDS_LIMIT = 'QUANTITY_EXCEEDS_LIMIT',
  TICKETS_SOLD_OUT = 'TICKETS_SOLD_OUT',
  SALES_NOT_STARTED = 'SALES_NOT_STARTED',
  SALES_ENDED = 'SALES_ENDED',
  INVALID_PROMO_CODE = 'INVALID_PROMO_CODE',
  PROMO_CODE_EXPIRED = 'PROMO_CODE_EXPIRED',

  // Payment errors (402)
  CARD_DECLINED = 'CARD_DECLINED',
  INSUFFICIENT_FUNDS = 'INSUFFICIENT_FUNDS',
  EXPIRED_CARD = 'EXPIRED_CARD',
  INCORRECT_CVC = 'INCORRECT_CVC',
  PROCESSING_ERROR = 'PROCESSING_ERROR',
  AUTHENTICATION_REQUIRED = 'AUTHENTICATION_REQUIRED',

  // Order errors (409)
  ORDER_EXPIRED = 'ORDER_EXPIRED',
  ORDER_ALREADY_PAID = 'ORDER_ALREADY_PAID',
  ORDER_CANCELLED = 'ORDER_CANCELLED',

  // Refund errors
  REFUND_EXCEEDS_PAYMENT = 'REFUND_EXCEEDS_PAYMENT',
  ALREADY_REFUNDED = 'ALREADY_REFUNDED',
  REFUND_NOT_ALLOWED = 'REFUND_NOT_ALLOWED',

  // System errors (500)
  PROVIDER_UNAVAILABLE = 'PROVIDER_UNAVAILABLE',
  INTERNAL_ERROR = 'INTERNAL_ERROR',
}
```

### 9.2 Stripe Error Mapping

```typescript
/**
 * Map Stripe error codes to our standardized errors
 */
function mapStripeError(stripeError: Stripe.errors.StripeError): PaymentError {
  const mapping: Record<string, PaymentError> = {
    'card_declined': {
      code: PaymentErrorCode.CARD_DECLINED,
      message: 'Your card was declined. Please try a different payment method.',
      retryable: true,
      suggestedAction: 'Try a different card or contact your bank.',
    },
    'insufficient_funds': {
      code: PaymentErrorCode.INSUFFICIENT_FUNDS,
      message: 'Insufficient funds. Please try a different payment method.',
      retryable: true,
      suggestedAction: 'Try a different card.',
    },
    'expired_card': {
      code: PaymentErrorCode.EXPIRED_CARD,
      message: 'Your card has expired. Please use a different card.',
      retryable: true,
      suggestedAction: 'Use a card with a valid expiration date.',
    },
    'incorrect_cvc': {
      code: PaymentErrorCode.INCORRECT_CVC,
      message: 'The security code is incorrect. Please check and try again.',
      retryable: true,
      suggestedAction: 'Check the 3-digit code on the back of your card.',
    },
    'authentication_required': {
      code: PaymentErrorCode.AUTHENTICATION_REQUIRED,
      message: 'Additional authentication required.',
      retryable: true,
      suggestedAction: 'Complete the authentication step with your bank.',
    },
    'rate_limit': {
      code: PaymentErrorCode.PROVIDER_UNAVAILABLE,
      message: 'Too many requests. Please try again in a moment.',
      retryable: true,
      suggestedAction: 'Wait a few seconds and try again.',
    },
  };

  return mapping[stripeError.code] ?? {
    code: PaymentErrorCode.PROCESSING_ERROR,
    message: 'Payment could not be processed. Please try again.',
    retryable: true,
    suggestedAction: 'Try again or use a different payment method.',
  };
}
```

### 9.3 Graceful Degradation

```yaml
Failure Scenarios and Handling:

1. Stripe API Unavailable:
   - Return friendly error to user
   - Log with high severity
   - Alert operations team
   - DO NOT show technical details to user

2. Webhook Processing Failure:
   - Return 500 to Stripe (triggers retry)
   - Log error with full context
   - Queue for manual review if retries exhausted

3. Database Unavailable:
   - Return 503 to user
   - DO NOT create payment intent (would orphan payment)
   - Implement circuit breaker

4. Partial Success (Order created, Payment failed):
   - Order remains in 'pending' status
   - User can retry payment
   - Expired orders cleaned up by job

5. Race Conditions (Duplicate submissions):
   - Use idempotency keys
   - Database constraints prevent duplicates
   - Return existing order if duplicate detected
```

---

## 10. Audit & Compliance

### 10.1 Required Audit Events

```typescript
/**
 * All these events MUST be logged to payment_audit_log
 */
enum AuditAction {
  // Order lifecycle
  ORDER_CREATED = 'order.created',
  ORDER_UPDATED = 'order.updated',
  ORDER_EXPIRED = 'order.expired',
  ORDER_CANCELLED = 'order.cancelled',
  ORDER_COMPLETED = 'order.completed',

  // Payment lifecycle
  PAYMENT_INTENT_CREATED = 'payment.intent_created',
  PAYMENT_INITIATED = 'payment.initiated',
  PAYMENT_PROCESSING = 'payment.processing',
  PAYMENT_SUCCEEDED = 'payment.succeeded',
  PAYMENT_FAILED = 'payment.failed',
  PAYMENT_CANCELLED = 'payment.cancelled',

  // Refund lifecycle
  REFUND_INITIATED = 'refund.initiated',
  REFUND_PROCESSING = 'refund.processing',
  REFUND_SUCCEEDED = 'refund.succeeded',
  REFUND_FAILED = 'refund.failed',
  REFUND_CANCELLED = 'refund.cancelled',

  // Promo code
  PROMO_CODE_APPLIED = 'promo_code.applied',
  PROMO_CODE_REMOVED = 'promo_code.removed',

  // Webhook
  WEBHOOK_RECEIVED = 'webhook.received',
  WEBHOOK_PROCESSED = 'webhook.processed',
  WEBHOOK_FAILED = 'webhook.failed',

  // Admin actions
  ADMIN_REFUND_OVERRIDE = 'admin.refund_override',
  ADMIN_ORDER_MODIFICATION = 'admin.order_modification',
}
```

### 10.2 Retention Requirements

```yaml
Data Retention Policy:

1. Audit Logs:
   - Retain indefinitely (legal requirement)
   - Archive to cold storage after 2 years
   - Never delete

2. Webhook Events:
   - Retain for 90 days in hot storage
   - Archive for 7 years (tax/legal)
   - Redact PII after archiving

3. Order/Payment Records:
   - Retain for 7 years (tax/accounting)
   - Soft delete only
   - Anonymize after retention period

4. Customer Data:
   - Subject to GDPR deletion requests
   - Pseudonymize where deletion conflicts with legal retention
```

### 10.3 Reconciliation

```yaml
Daily Reconciliation Process:

1. Fetch all payments from Stripe for date range
2. Compare with local payment records
3. Flag discrepancies:
   - Payments in Stripe not in database
   - Payments in database not in Stripe
   - Amount mismatches
   - Status mismatches

4. Auto-resolve where possible:
   - Missing webhook → fetch and process
   - Status mismatch → update from Stripe

5. Manual review queue for unresolved issues

6. Generate reconciliation report

Frequency: Run daily at 2 AM UTC
```

---

## 11. Testing Requirements

### 11.1 Test Coverage Requirements

```yaml
Minimum Test Coverage:

1. Unit Tests (>90% coverage):
   - Payment provider interface
   - Amount calculations
   - Currency handling
   - Error mapping
   - Validation functions

2. Integration Tests:
   - Stripe API calls (use test mode)
   - Webhook processing
   - Database transactions
   - Idempotency behavior

3. End-to-End Tests:
   - Complete checkout flow
   - Successful payment
   - Failed payment scenarios
   - Refund flow
   - Promo code application

4. Security Tests:
   - Webhook signature verification
   - Invalid signature rejection
   - Replay attack prevention
   - Input validation
```

### 11.2 Stripe Test Cards

```yaml
Use these test cards in development/staging:

Success Cases:
  - 4242 4242 4242 4242 → Succeeds
  - 4000 0025 0000 3155 → Requires 3D Secure
  - 4000 0000 0000 3220 → 3D Secure 2 authentication

Decline Cases:
  - 4000 0000 0000 9995 → Insufficient funds
  - 4000 0000 0000 9987 → Lost card
  - 4000 0000 0000 9979 → Stolen card
  - 4000 0000 0000 0002 → Generic decline
  - 4000 0000 0000 0069 → Expired card
  - 4000 0000 0000 0127 → Incorrect CVC

Fraud Prevention:
  - 4100 0000 0000 0019 → Highest risk (blocked)
  - 4000 0000 0000 0101 → CVC check fails

All test cards:
  - Use any future expiry date
  - Use any 3-digit CVC
  - Use any postal code
```

### 11.3 Webhook Testing

```yaml
Testing Webhooks Locally:

1. Install Stripe CLI:
   stripe login

2. Forward webhooks to local server:
   stripe listen --forward-to localhost:3000/api/webhooks/stripe

3. Trigger test events:
   stripe trigger payment_intent.succeeded
   stripe trigger payment_intent.payment_failed
   stripe trigger charge.refunded

4. Verify:
   - Events logged to database
   - Orders updated correctly
   - Audit log entries created
```

---

## 12. Implementation Checklist

### Phase 1: Foundation
- [ ] Create database tables with migrations
- [ ] Implement PaymentProviderInterface
- [ ] Implement StripeProvider
- [ ] Set up environment variables
- [ ] Create audit logging service

### Phase 2: Order Flow
- [ ] Implement order creation
- [ ] Implement payment intent creation
- [ ] Implement order expiration job
- [ ] Create GraphQL schema and resolvers

### Phase 3: Webhooks
- [ ] Set up webhook endpoint
- [ ] Implement signature verification
- [ ] Implement event handlers
- [ ] Set up retry mechanism
- [ ] Implement reconciliation job

### Phase 4: Refunds
- [ ] Implement refund creation
- [ ] Implement refund webhooks
- [ ] Implement partial refunds
- [ ] Add admin UI for refunds

### Phase 5: Testing & Monitoring
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Set up monitoring/alerting
- [ ] Create runbook for common issues
- [ ] Load testing

---

## Appendix A: Environment Variables Template

```bash
# .env.example (DO NOT COMMIT ACTUAL VALUES)

# Payment Mode
PAYMENT_MODE=test  # 'test' or 'live'

# Stripe Configuration
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Stripe Production (use in production only)
# STRIPE_PUBLISHABLE_KEY=pk_live_xxx
# STRIPE_SECRET_KEY=sk_live_xxx
# STRIPE_WEBHOOK_SECRET=whsec_xxx

# Stripe Settings
STRIPE_API_VERSION=2023-10-16
STRIPE_MAX_NETWORK_RETRIES=2

# Order Settings
ORDER_EXPIRY_MINUTES=30
MINIMUM_TICKET_PRICE_CENTS=50

# Platform Settings
PLATFORM_FEE_PERCENT=2.5
PLATFORM_FEE_FIXED_CENTS=30
```

---

## Appendix B: GraphQL Frontend Implementation Notes

When the backend is ready, the frontend will need:

1. **Stripe.js SDK**: Load via `@stripe/stripe-js`
2. **Stripe Elements**: Use `@stripe/react-stripe-js` for card input
3. **Checkout Flow**:
   - Call `createCheckoutSession` mutation
   - Get `clientSecret` from response
   - Confirm payment with Stripe.js
   - Handle success/error

This document provides complete backend specifications. Frontend implementation will be a separate phase.

---

*End of Document*
