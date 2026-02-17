# Stripe Connect & Enterprise Ticketing — Full Implementation Plan

> **Purpose**: This document defines everything that needs to be built to make the ticketing/payment system production-ready with proper multi-party payments via Stripe Connect. Each phase is self-contained and can be assigned to a separate agent.

---

## Current State Summary

| Area | Status |
|---|---|
| Ticket creation/management (organizer) | Working |
| Ticket purchasing (attendee) | Working — but all money goes to platform's Stripe account |
| Stripe Connect (marketplace payments) | Provider code exists, but NOT wired up |
| Organizer Stripe onboarding | Not built (no API, no UI) |
| Platform fees | Database columns exist, hardcoded to $0 |
| Organizer payout visibility | Not built |
| Platform admin panel | Does not exist |
| Webhook handling for Connect events | Not built |
| Fee absorption model (who pays fees) | Not implemented |

---

## Platform Fee Model (Business Logic)

### Default Fee Structure
```
Per paid ticket sold:
  Platform fee:        4% + $0.75 per ticket
  Stripe processing:   2.9% + $0.30 (Stripe takes this automatically)
  Free event tickets:  $0.00 (no fees)
```

### Fee Absorption Options (organizer chooses per event)
- **absorb**: Fees deducted from organizer's revenue. Attendee pays ticket face value.
- **pass_to_buyer**: Fees added on top. Attendee pays ticket price + fees. Organizer receives full face value.

### Fee Calculation Example ($50 ticket)

**Absorb model:**
```
Attendee pays:      $50.00
Stripe fee:         -$1.75   (2.9% + $0.30)
Platform fee:       -$2.75   (4% + $0.75)
Organizer receives: $45.50
```

**Pass-to-buyer model:**
```
Ticket price:       $50.00
Platform fee:       +$2.75   (4% + $0.75)
Stripe fee:         +$1.83   (2.9% of $52.75 + $0.30)
Attendee pays:      $54.58
Organizer receives: $50.00
```

---

## Phase 1: Stripe Connect Onboarding (Backend)

> **Goal**: Allow organizers to connect their Stripe account to the platform so they can receive ticket revenue.

### 1.1 New Environment Variables

**File**: `event-lifecycle-service/.env.example`
**File**: `event-lifecycle-service/app/core/config.py`

Add:
```
STRIPE_CONNECT_CLIENT_ID=ca_xxxxxxxxxxxx
STRIPE_CONNECT_WEBHOOK_SECRET=whsec_connect_xxxxxxxxxxxx
PLATFORM_FEE_PERCENT=4.0
PLATFORM_FEE_FIXED_CENTS=75
PLATFORM_NAME=GlobalConnect
PLATFORM_SUPPORT_EMAIL=support@globalconnect.com
```

### 1.2 Stripe Connect Service

**New file**: `event-lifecycle-service/app/services/payment/stripe_connect_service.py`

This service handles all Stripe Connect account lifecycle operations:

```python
class StripeConnectService:
    """
    Manages Stripe Connect Express accounts for organizers.
    """

    async def create_connected_account(
        self,
        organization_id: str,
        organization_name: str,
        email: str,
        country: str = "US",  # ISO 3166-1 alpha-2
    ) -> dict:
        """
        Creates a Stripe Express connected account for an organization.

        Calls: stripe.Account.create(type="express", ...)
        Stores: connected_account_id in organization_payment_settings
        Returns: { account_id, onboarding_url }
        """

    async def create_onboarding_link(
        self,
        organization_id: str,
        refresh_url: str,
        return_url: str,
    ) -> str:
        """
        Generates a Stripe AccountLink for the organizer to complete onboarding.
        Used when: first-time setup OR re-verification needed.

        Calls: stripe.AccountLink.create(
            account=connected_account_id,
            type="account_onboarding",
            refresh_url=refresh_url,
            return_url=return_url,
        )
        Returns: onboarding URL (short-lived, must be used immediately)
        """

    async def create_login_link(
        self,
        organization_id: str,
    ) -> str:
        """
        Generates a Stripe Express Dashboard login link for the organizer
        to view payouts, balances, and transaction history.

        Calls: stripe.Account.create_login_link(connected_account_id)
        Returns: dashboard URL
        """

    async def get_account_status(
        self,
        organization_id: str,
    ) -> dict:
        """
        Retrieves the connected account's current status.

        Calls: stripe.Account.retrieve(connected_account_id)
        Returns: {
            account_id,
            charges_enabled: bool,     # Can accept payments
            payouts_enabled: bool,     # Can receive payouts
            details_submitted: bool,   # Completed onboarding form
            requirements: {            # Outstanding verification items
                currently_due: [],
                eventually_due: [],
                past_due: [],
                disabled_reason: str | None,
            },
            verified: bool,  # charges_enabled AND payouts_enabled
        }
        """

    async def get_account_balance(
        self,
        organization_id: str,
    ) -> dict:
        """
        Gets the connected account's balance.

        Calls: stripe.Balance.retrieve(stripe_account=connected_account_id)
        Returns: { available: [...], pending: [...] }
        """

    async def update_payout_schedule(
        self,
        organization_id: str,
        interval: str,  # "daily", "weekly", "monthly", "manual"
        weekly_anchor: str | None = None,  # "monday", "tuesday", etc.
        monthly_anchor: int | None = None,  # 1-31
    ) -> dict:
        """
        Updates the payout schedule for a connected account.

        Calls: stripe.Account.modify(connected_account_id, settings={payouts: {schedule: {...}}})
        """

    async def deauthorize_account(
        self,
        organization_id: str,
    ) -> None:
        """
        Disconnects a connected account from the platform.
        Does NOT delete the Stripe account — organizer keeps it.

        Calls: stripe.OAuth.deauthorize(client_id=..., stripe_user_id=connected_account_id)
        Updates: organization_payment_settings.is_active = False
        """
```

### 1.3 GraphQL Mutations & Queries for Connect

**New file**: `event-lifecycle-service/app/graphql/connect_mutations.py`
**New file**: `event-lifecycle-service/app/graphql/connect_queries.py`

**Mutations:**
```graphql
type Mutation {
  # Creates a Stripe Express account and returns onboarding URL
  # Auth: OWNER or ADMIN of the organization
  createStripeConnectAccount(
    organizationId: ID!
    country: String        # defaults to "US"
  ): ConnectOnboardingResult!

  # Generates a new onboarding link (if previous expired or needs re-verification)
  # Auth: OWNER or ADMIN
  createStripeOnboardingLink(
    organizationId: ID!
  ): ConnectOnboardingLink!

  # Generates a Stripe Express Dashboard login link
  # Auth: OWNER or ADMIN
  createStripeDashboardLink(
    organizationId: ID!
  ): StripeDashboardLink!

  # Updates payout schedule preferences
  # Auth: OWNER or ADMIN
  updatePayoutSchedule(
    organizationId: ID!
    interval: PayoutInterval!        # DAILY, WEEKLY, MONTHLY, MANUAL
    weeklyAnchor: DayOfWeek          # Required if interval=WEEKLY
    monthlyAnchor: Int               # Required if interval=MONTHLY (1-31)
  ): PayoutSchedule!

  # Disconnects Stripe account (organizer keeps their Stripe account)
  # Auth: OWNER only
  disconnectStripeAccount(
    organizationId: ID!
  ): Boolean!

  # PLATFORM ADMIN: Override fee for a specific organization
  # Auth: Platform super-admin
  updateOrganizationFees(
    organizationId: ID!
    platformFeePercent: Float!   # e.g., 3.5
    platformFeeFixed: Int!       # in cents, e.g., 75
  ): OrganizationPaymentSettings!
}
```

**Queries:**
```graphql
type Query {
  # Get organization's Stripe Connect status
  # Auth: OWNER or ADMIN of the organization
  organizationPaymentStatus(
    organizationId: ID!
  ): OrganizationPaymentStatus!

  # Get connected account balance
  # Auth: OWNER or ADMIN
  organizationBalance(
    organizationId: ID!
  ): AccountBalance!

  # Get platform fee configuration for an organization
  # Auth: OWNER or ADMIN
  organizationFees(
    organizationId: ID!
  ): FeeConfiguration!
}
```

**Types:**
```graphql
type ConnectOnboardingResult {
  accountId: String!
  onboardingUrl: String!
}

type ConnectOnboardingLink {
  url: String!
  expiresAt: DateTime!
}

type StripeDashboardLink {
  url: String!
}

type OrganizationPaymentStatus {
  isConnected: Boolean!
  accountId: String
  chargesEnabled: Boolean!
  payoutsEnabled: Boolean!
  detailsSubmitted: Boolean!
  verified: Boolean!           # fully ready to accept payments
  requirements: AccountRequirements
}

type AccountRequirements {
  currentlyDue: [String!]!
  eventuallyDue: [String!]!
  pastDue: [String!]!
  disabledReason: String
}

type AccountBalance {
  available: [BalanceAmount!]!
  pending: [BalanceAmount!]!
}

type BalanceAmount {
  amount: Int!           # in cents
  currency: String!
}

type FeeConfiguration {
  platformFeePercent: Float!    # e.g., 4.0
  platformFeeFixed: Int!        # in cents, e.g., 75
  feeAbsorption: FeeAbsorption! # ORGANIZER_ABSORBS or PASS_TO_BUYER
  effectiveDate: DateTime
}

enum PayoutInterval {
  DAILY
  WEEKLY
  MONTHLY
  MANUAL
}

enum DayOfWeek {
  MONDAY
  TUESDAY
  WEDNESDAY
  THURSDAY
  FRIDAY
}

enum FeeAbsorption {
  ORGANIZER_ABSORBS
  PASS_TO_BUYER
}
```

### 1.4 REST Endpoints for Stripe Connect Webhooks

**New file or extend**: `event-lifecycle-service/app/api/v1/endpoints/connect_webhooks.py`

**Route**: `POST /api/webhooks/stripe-connect`

This endpoint uses a **separate webhook secret** (`STRIPE_CONNECT_WEBHOOK_SECRET`) from the main payment webhooks because Stripe Connect events are delivered to a different webhook endpoint.

**Events to handle:**

| Event | Action |
|---|---|
| `account.updated` | Update `organization_payment_settings` — sync `charges_enabled`, `payouts_enabled`, `verified_at`. If account becomes restricted, flag it. |
| `account.application.deauthorized` | Mark `organization_payment_settings.is_active = False`. Organizer disconnected from their Stripe dashboard. |
| `payout.paid` | Log successful payout for organizer visibility. Store in new `organizer_payouts` table. |
| `payout.failed` | Log failed payout. Notify organizer (email via Kafka). |
| `capability.updated` | Track capability changes (card_payments, transfers). |

### 1.5 Database Migration

**New migration**: `alembic/versions/p003_stripe_connect_enhancements.py`

Changes to `organization_payment_settings`:
```sql
-- Add columns
ALTER TABLE organization_payment_settings ADD COLUMN country VARCHAR(2) DEFAULT 'US';
ALTER TABLE organization_payment_settings ADD COLUMN charges_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE organization_payment_settings ADD COLUMN payouts_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE organization_payment_settings ADD COLUMN details_submitted BOOLEAN DEFAULT FALSE;
ALTER TABLE organization_payment_settings ADD COLUMN requirements_json JSONB DEFAULT '{}';
ALTER TABLE organization_payment_settings ADD COLUMN fee_absorption VARCHAR(20) DEFAULT 'absorb';
ALTER TABLE organization_payment_settings ADD COLUMN onboarding_completed_at TIMESTAMPTZ;
ALTER TABLE organization_payment_settings ADD COLUMN deauthorized_at TIMESTAMPTZ;
```

New table `organizer_payouts`:
```sql
CREATE TABLE organizer_payouts (
    id VARCHAR PRIMARY KEY,
    organization_id VARCHAR NOT NULL,
    stripe_payout_id VARCHAR NOT NULL UNIQUE,
    amount INTEGER NOT NULL,           -- in cents
    currency VARCHAR(3) NOT NULL,
    status VARCHAR(20) NOT NULL,       -- paid, failed, pending, canceled
    arrival_date TIMESTAMPTZ,
    failure_code VARCHAR(100),
    failure_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT fk_org FOREIGN KEY (organization_id)
        REFERENCES organization_payment_settings(organization_id)
);

CREATE INDEX idx_payouts_org ON organizer_payouts(organization_id);
CREATE INDEX idx_payouts_status ON organizer_payouts(status);
```

### 1.6 Ticket Sales Gating

**Modify**: `event-lifecycle-service/app/services/payment/payment_service.py`

Before creating a checkout session, check if the organizer has a verified connected account:

```python
# In create_checkout_session(), before processing:
if total_amount > 0:  # Only for paid tickets
    org_settings = await self._get_org_payment_settings(organization_id, db)
    if not org_settings or not org_settings.connected_account_id:
        raise PaymentError(
            "ORGANIZER_NOT_CONNECTED",
            "This organizer has not connected their payment account. "
            "Ticket purchases are temporarily unavailable."
        )
    if not org_settings.charges_enabled:
        raise PaymentError(
            "ORGANIZER_ACCOUNT_RESTRICTED",
            "The organizer's payment account is under review. "
            "Please try again later."
        )
```

**Modify**: `event-lifecycle-service/app/graphql/ticket_queries.py`

Add a `paymentReady` field to the `TicketType` GraphQL type so the frontend can show appropriate messaging when an organizer hasn't connected Stripe:

```graphql
type TicketType {
  # ... existing fields ...
  paymentReady: Boolean!  # True if organizer's Stripe is connected + verified
}
```

---

## Phase 2: Wire Up Platform Fees & Destination Charges (Backend)

> **Goal**: Make the payment service use Stripe Connect destination charges with calculated platform fees, so money flows to organizers.

### 2.1 Fee Calculation Service

**New file**: `event-lifecycle-service/app/services/payment/fee_calculator.py`

```python
class FeeCalculator:
    """
    Calculates platform fees for ticket orders.

    Fee model:
    - platform_fee = (ticket_price * platform_fee_percent / 100) + platform_fee_fixed
    - Applied PER TICKET (not per order)
    - Free tickets ($0) have no fees
    """

    def __init__(self, default_percent: float, default_fixed_cents: int):
        """
        Args:
            default_percent: Default platform fee percentage (e.g., 4.0 for 4%)
            default_fixed_cents: Default fixed fee per ticket in cents (e.g., 75 for $0.75)
        """

    def calculate_order_fees(
        self,
        items: list[OrderItemData],
        org_settings: OrganizationPaymentSettings | None,
    ) -> FeeBreakdown:
        """
        Calculate fees for an entire order.

        Uses org-specific overrides if available, otherwise defaults.

        Returns:
            FeeBreakdown(
                platform_fee_total: int,       # Total platform fee in cents
                per_item_fees: list[ItemFee],  # Per-item breakdown
                fee_percent_used: float,       # The percentage that was applied
                fee_fixed_used: int,           # The fixed fee that was applied
                absorption_model: str,         # "absorb" or "pass_to_buyer"
            )
        """

    def calculate_buyer_total(
        self,
        subtotal: int,
        platform_fee_total: int,
        absorption_model: str,
    ) -> int:
        """
        If pass_to_buyer: returns subtotal + platform_fee_total
        If absorb: returns subtotal (fees come from organizer's share)
        """
```

### 2.2 Modify PaymentService to Use Connect

**File**: `event-lifecycle-service/app/services/payment/payment_service.py`

**Change 1**: Query org payment settings during checkout

```python
# BEFORE (current):
platform_fee=0,  # TODO: Calculate platform fee

# AFTER:
org_settings = await self._get_org_payment_settings(organization_id, db)
fee_breakdown = self.fee_calculator.calculate_order_fees(order_items, org_settings)
platform_fee = fee_breakdown.platform_fee_total
```

**Change 2**: Pass Connect params to CreatePaymentIntentParams

```python
# BEFORE (current):
intent_params = CreatePaymentIntentParams(
    order_id=order.id,
    amount=total_amount,
    currency=currency,
    ...
)

# AFTER:
buyer_total = self.fee_calculator.calculate_buyer_total(
    subtotal=total_amount,
    platform_fee_total=fee_breakdown.platform_fee_total,
    absorption_model=org_settings.fee_absorption if org_settings else "absorb",
)

intent_params = CreatePaymentIntentParams(
    order_id=order.id,
    amount=buyer_total,  # May differ from subtotal in pass_to_buyer model
    currency=currency,
    connected_account_id=org_settings.connected_account_id if org_settings else None,
    platform_fee_amount=fee_breakdown.platform_fee_total if org_settings else None,
    ...
)
```

**Change 3**: Store fee breakdown in order

```python
order_create = OrderCreate(
    ...
    platform_fee=fee_breakdown.platform_fee_total,
    subtotal_amount=total_amount,        # Original ticket prices
    total_amount=buyer_total,            # What the attendee actually pays
    fee_absorption=org_settings.fee_absorption if org_settings else "absorb",
    ...
)
```

### 2.3 Refund Handling with Connect

**File**: `event-lifecycle-service/app/services/payment/payment_service.py` (refund methods)
**File**: `event-lifecycle-service/app/services/payment/providers/stripe_provider.py` (refund call)

When refunding a destination charge:
- **Full refund**: Refund the full amount to the buyer. Stripe automatically reverses the transfer to the organizer. The platform fee (application_fee) is refunded by default.
- **Partial refund**: Specify `refund_application_fee=True/False` to control whether the platform keeps its fee.

```python
# In stripe_provider.py, modify create_refund:
refund_params = {
    "payment_intent": payment_intent_id,
    "amount": amount,  # None for full refund
}

# If this was a Connect payment, handle application fee refund
if refund_application_fee is not None:
    refund_params["refund_application_fee"] = refund_application_fee

# For Connect payments, Stripe auto-reverses transfer proportionally
# No need to manually reverse — Stripe handles this
```

### 2.4 Order Schema Migration

**New migration**: `alembic/versions/p004_add_fee_fields_to_orders.py`

```sql
ALTER TABLE orders ADD COLUMN subtotal_amount INTEGER;
ALTER TABLE orders ADD COLUMN fee_absorption VARCHAR(20) DEFAULT 'absorb';
ALTER TABLE orders ADD COLUMN fee_breakdown_json JSONB DEFAULT '{}';
ALTER TABLE orders ADD COLUMN connected_account_id VARCHAR(255);

-- Backfill: set subtotal_amount = total_amount for existing orders
UPDATE orders SET subtotal_amount = total_amount WHERE subtotal_amount IS NULL;
```

### 2.5 Update GraphQL Types for Fee Display

**File**: `event-lifecycle-service/app/graphql/payment_types.py`

Add fee transparency to the checkout and order types:

```graphql
type CheckoutSession {
  # ... existing fields ...
  subtotalAmount: Int!           # Ticket prices before fees
  platformFee: Int!              # Platform fee amount
  processingFee: Int!            # Estimated Stripe processing fee
  totalAmount: Int!              # What the attendee pays
  feeAbsorption: FeeAbsorption!  # Who pays the fees
}

type Order {
  # ... existing fields ...
  subtotalAmount: Int!
  platformFee: Int!
  feeAbsorption: FeeAbsorption!
  feeBreakdown: FeeBreakdown
}

type FeeBreakdown {
  platformFeePercent: Float!
  platformFeeFixed: Int!
  platformFeeTotal: Int!
  perItemFees: [ItemFee!]!
}

type ItemFee {
  ticketTypeName: String!
  quantity: Int!
  unitPrice: Int!
  feePerTicket: Int!
  feeSubtotal: Int!
}
```

---

## Phase 3: Frontend — Organizer Stripe Onboarding UI

> **Goal**: Build the UI for organizers to connect their Stripe account and manage payment settings.

### 3.1 New Dashboard Page: Payment Settings

**New file**: `globalconnect/src/app/(platform)/dashboard/settings/payments/page.tsx`

This page contains:

1. **Stripe Connect Card**
   - If NOT connected: "Connect with Stripe" button → calls `createStripeConnectAccount` mutation → redirects to Stripe onboarding
   - If connected but NOT verified: "Complete Verification" button + status indicator showing what's pending
   - If connected AND verified: Green checkmark, account ID (masked), "View Stripe Dashboard" button

2. **Payout Schedule Card** (only shown when connected)
   - Dropdown: Daily / Weekly / Monthly / Manual
   - Day picker for weekly (Mon-Fri) or monthly (1-31)
   - Save button → calls `updatePayoutSchedule` mutation

3. **Fee Information Card** (read-only)
   - Shows current platform fee rate: "4% + $0.75 per paid ticket"
   - Shows fee absorption model with toggle: "Absorb fees" / "Pass to buyer"
   - Example calculation based on a sample ticket price

4. **Balance Overview Card** (only when connected)
   - Available balance
   - Pending balance
   - "View full details in Stripe" link → calls `createStripeDashboardLink`

5. **Disconnect Section**
   - "Disconnect Stripe Account" with confirmation dialog
   - Warning: "Active ticket sales will be paused until a new account is connected"

### 3.2 Stripe Connect Return/Refresh Pages

**New file**: `globalconnect/src/app/(platform)/dashboard/settings/payments/return/page.tsx`
- Stripe redirects here after onboarding is completed
- Calls `organizationPaymentStatus` query to check verification status
- Shows success/pending/needs-more-info messaging

**New file**: `globalconnect/src/app/(platform)/dashboard/settings/payments/refresh/page.tsx`
- Stripe redirects here if the onboarding link expired
- Auto-generates a new onboarding link and redirects back to Stripe

### 3.3 Onboarding Prompt in Event Dashboard

**Modify**: `globalconnect/src/app/(platform)/dashboard/events/[eventId]/_components/ticket-management.tsx`

Add a banner at the top of ticket management if the organizer hasn't connected Stripe:

```
┌─────────────────────────────────────────────────────────┐
│  ⚠ Connect your Stripe account to start selling tickets │
│                                                         │
│  You need to connect a Stripe account before attendees  │
│  can purchase paid tickets for your events.             │
│                                                         │
│  [Connect with Stripe]                                  │
└─────────────────────────────────────────────────────────┘
```

Free tickets should still work without Stripe connected.

### 3.4 Checkout Fee Display

**Modify**: `globalconnect/src/components/features/checkout/ticket-selector.tsx`

Show fee breakdown in the order summary:

```
Order Summary
─────────────────────────────
2x VIP Ticket           $100.00
1x General Admission     $25.00
─────────────────────────────
Subtotal                $125.00
Service fee               $7.25    ← Only shown in pass_to_buyer model
─────────────────────────────
Total                   $132.25
```

In "absorb" model, no fee line is shown — the attendee just sees the ticket prices.

### 3.5 GraphQL Operations

**New file**: `globalconnect/src/graphql/connect.graphql.ts`

```typescript
// Mutations
CREATE_STRIPE_CONNECT_ACCOUNT_MUTATION
CREATE_STRIPE_ONBOARDING_LINK_MUTATION
CREATE_STRIPE_DASHBOARD_LINK_MUTATION
UPDATE_PAYOUT_SCHEDULE_MUTATION
UPDATE_FEE_ABSORPTION_MUTATION
DISCONNECT_STRIPE_ACCOUNT_MUTATION

// Queries
ORGANIZATION_PAYMENT_STATUS_QUERY
ORGANIZATION_BALANCE_QUERY
ORGANIZATION_FEES_QUERY
```

### 3.6 Custom Hook

**New file**: `globalconnect/src/hooks/use-stripe-connect.ts`

```typescript
export function useStripeConnect(organizationId: string) {
  // Returns:
  // - paymentStatus: { isConnected, chargesEnabled, payoutsEnabled, verified, requirements }
  // - balance: { available, pending }
  // - fees: { platformFeePercent, platformFeeFixed, feeAbsorption }
  // - actions: { connectAccount, createOnboardingLink, openDashboard, disconnect, updatePayoutSchedule, updateFeeAbsorption }
  // - loading, error states
}
```

---

## Phase 4: Attendee Ticket Purchase Page (Public-Facing)

> **Goal**: Build/enhance the public event page ticket purchase experience with fee transparency and proper payment status handling.

### 4.1 Enhanced Ticket Display on Event Page

**Modify**: `globalconnect/src/app/(public)/events/[eventId]/page.tsx` (or relevant component)

The public event page should show:
- Ticket types with prices
- "Service fee" note if pass_to_buyer model
- Sold out / limited stock indicators
- "Sales start on [date]" / "Sales end on [date]"
- If organizer hasn't connected Stripe: "Tickets coming soon" (not an error)

### 4.2 Checkout Flow Enhancement

**Modify**: `globalconnect/src/components/features/checkout/payment-form.tsx`

After successful payment, show:
- Order confirmation with ticket details
- QR code for each ticket (if already generated)
- "Tickets sent to [email]" confirmation
- Order number for reference

**Modify**: `globalconnect/src/app/(public)/events/[eventId]/checkout/confirmation/page.tsx`

Enhance confirmation page with:
- Fee breakdown (subtotal, service fee if applicable, total)
- Download tickets / Add to calendar buttons
- Order status tracking

### 4.3 Error States

Handle these checkout error states gracefully in the frontend:
- `ORGANIZER_NOT_CONNECTED`: "Tickets are not yet available for purchase. Please check back later."
- `ORGANIZER_ACCOUNT_RESTRICTED`: "Ticket sales are temporarily paused. Please try again later."
- `TICKET_SOLD_OUT`: "Sorry, this ticket type is sold out."
- `RESERVATION_EXPIRED`: "Your reservation has expired. Please try again."
- `PAYMENT_FAILED`: "Payment was declined. Please try a different payment method."

---

## Phase 5: Platform Admin Panel

> **Goal**: Build a platform-level admin interface for managing organizations, fees, and monitoring revenue.

### 5.1 Admin Authentication

**Modify**: `user-and-org-service/prisma/schema.prisma`

Add a platform-level super admin concept:

```prisma
model User {
  // ... existing fields ...
  isPlatformAdmin  Boolean  @default(false)
}
```

**New guard/middleware**: Check `isPlatformAdmin` for admin routes. This is separate from organization roles — a platform admin can manage ALL organizations.

### 5.2 Admin Dashboard Pages

**New route group**: `globalconnect/src/app/(admin)/`

Pages:

| Page | Path | Purpose |
|---|---|---|
| Admin Home | `/admin` | Overview: total revenue, active orgs, ticket sales volume |
| Organizations | `/admin/organizations` | List all orgs with Stripe Connect status |
| Org Detail | `/admin/organizations/[orgId]` | Manage fees, view transactions, Stripe status |
| Revenue | `/admin/revenue` | Platform fee revenue, charts, trends |
| Transactions | `/admin/transactions` | All ticket purchases across the platform |
| Payouts | `/admin/payouts` | Organizer payout status and history |
| Fee Config | `/admin/settings/fees` | Default fee configuration |
| Disputes | `/admin/disputes` | Stripe disputes/chargebacks across the platform |

### 5.3 Admin GraphQL Schema

**New files**: `event-lifecycle-service/app/graphql/admin_queries.py`, `admin_mutations.py`

```graphql
type Query {
  # All require isPlatformAdmin auth

  adminDashboardStats: AdminDashboardStats!
  adminOrganizations(
    page: Int
    limit: Int
    search: String
    stripeStatus: StripeConnectionStatus   # CONNECTED, PENDING, NOT_CONNECTED
  ): PaginatedOrganizations!

  adminOrganizationDetail(organizationId: ID!): AdminOrganizationDetail!

  adminTransactions(
    page: Int
    limit: Int
    organizationId: ID
    dateFrom: DateTime
    dateTo: DateTime
    status: OrderStatus
  ): PaginatedTransactions!

  adminRevenueReport(
    period: ReportPeriod!  # DAILY, WEEKLY, MONTHLY
    dateFrom: DateTime!
    dateTo: DateTime!
  ): RevenueReport!

  adminPayouts(
    page: Int
    limit: Int
    organizationId: ID
    status: PayoutStatus
  ): PaginatedPayouts!
}

type Mutation {
  # Override fees for a specific org (e.g., negotiated enterprise rate)
  adminSetOrganizationFees(
    organizationId: ID!
    platformFeePercent: Float!
    platformFeeFixed: Int!
  ): OrganizationPaymentSettings!

  # Update default platform fees
  adminSetDefaultFees(
    platformFeePercent: Float!
    platformFeeFixed: Int!
  ): DefaultFeeConfig!

  # Flag/unflag an organization
  adminFlagOrganization(
    organizationId: ID!
    reason: String!
  ): Boolean!
}

type AdminDashboardStats {
  totalRevenue: Int!               # Total platform fees collected (cents)
  totalGMV: Int!                   # Gross merchandise value
  totalOrganizations: Int!
  connectedOrganizations: Int!     # With verified Stripe
  totalTicketsSold: Int!
  totalEvents: Int!
  revenueThisMonth: Int!
  revenueLastMonth: Int!
  growthPercent: Float!
}

type AdminOrganizationDetail {
  id: ID!
  name: String!
  stripeStatus: OrganizationPaymentStatus!
  totalRevenue: Int!               # GMV through this org
  platformFeesCollected: Int!      # Platform fees from this org
  totalTicketsSold: Int!
  totalEvents: Int!
  feeOverride: FeeConfiguration    # Null if using defaults
  recentTransactions: [Order!]!
}
```

### 5.4 Revenue Reporting Database Views

**New migration**: `alembic/versions/p005_create_revenue_views.py`

```sql
-- Daily platform revenue aggregation
CREATE MATERIALIZED VIEW platform_daily_revenue AS
SELECT
    DATE(o.completed_at) AS date,
    o.organization_id,
    COUNT(*) AS order_count,
    SUM(o.total_amount) AS gmv,           -- Gross merchandise value
    SUM(o.platform_fee) AS platform_fees,
    SUM(o.total_amount - o.platform_fee) AS organizer_revenue,
    o.currency
FROM orders o
WHERE o.status = 'completed'
GROUP BY DATE(o.completed_at), o.organization_id, o.currency;

CREATE UNIQUE INDEX idx_daily_revenue ON platform_daily_revenue(date, organization_id, currency);

-- Refresh this view periodically (via cron/Celery task)
```

---

## Phase 6: Email Notifications

> **Goal**: Send transactional emails for payment-related events via the existing Kafka email pipeline.

### 6.1 New Email Templates (via Kafka → email-consumer-worker)

| Trigger | Recipient | Template | Content |
|---|---|---|---|
| Stripe onboarding complete | Organizer | `stripe_connected` | "Your payment account is verified. You can now sell tickets." |
| Stripe account restricted | Organizer | `stripe_restricted` | "Action required: Your payment account needs attention." |
| Ticket purchased | Attendee | `ticket_confirmation` | Order details, ticket QR codes, event info |
| Ticket purchased | Organizer | `new_ticket_sale` | "You sold 2 tickets for [Event]. Revenue: $X" |
| Refund processed | Attendee | `refund_confirmation` | Refund amount, original order reference |
| Payout sent | Organizer | `payout_sent` | "Payout of $X is on its way to your bank account" |
| Payout failed | Organizer | `payout_failed` | "Payout of $X failed. Please update your bank details." |

### 6.2 Kafka Event Production

Publish to existing Kafka topics from the relevant services when these events occur. The email-consumer-worker already consumes and sends via Resend.

---

## Phase 7: Testing & Hardening

> **Goal**: Ensure production reliability.

### 7.1 Unit Tests

**New tests in**: `event-lifecycle-service/tests/`

| Test File | What It Tests |
|---|---|
| `test_fee_calculator.py` | Fee calculation: percentage, fixed, combined, zero-price tickets, rounding, org overrides |
| `test_stripe_connect_service.py` | Account creation, onboarding links, status checks (mock Stripe API) |
| `test_payment_service_connect.py` | End-to-end checkout with Connect params, fee absorption models |
| `test_connect_webhooks.py` | account.updated, payout.paid/failed handlers |
| `test_refund_with_connect.py` | Refunds with and without application fee refund |

### 7.2 Stripe Test Mode

- All development uses `sk_test_` and `pk_test_` keys
- Use Stripe CLI (`stripe listen --forward-to localhost:8000/api/webhooks/stripe-connect`) for local webhook testing
- Test card numbers: `4242424242424242` (success), `4000000000000002` (decline)
- Test Connect accounts: Create test Express accounts in Stripe dashboard

### 7.3 Idempotency

All Stripe API calls must use idempotency keys (already implemented for PaymentIntents — extend to Account creation, refunds, etc.).

### 7.4 Error Handling

- Stripe API errors → catch `stripe.error.StripeError` subtypes
- Rate limiting → exponential backoff with jitter
- Webhook replay → idempotent processing (already exists via `payment_webhook_events` table — extend for Connect events)

### 7.5 Security

- Connected account IDs are sensitive — never expose full IDs in frontend (mask as `acct_xxxx...xxxx`)
- Webhook signature verification is mandatory (already implemented — extend for Connect webhook endpoint)
- Only OWNER/ADMIN roles can manage payment settings
- Platform admin actions require `isPlatformAdmin` flag
- All financial operations logged in `payment_audit_log`

---

## Phase 8: Stripe Dashboard Configuration

> **Goal**: Document the Stripe dashboard setup required before deployment.

### 8.1 Stripe Account Setup (One-Time)

1. **Enable Stripe Connect** in your Stripe dashboard → Settings → Connect
2. **Set platform profile**: Upload logo, set platform name, support URL
3. **Choose Express accounts** as the default connected account type
4. **Configure branding** for the Express onboarding flow (colors, logo)
5. **Set Connect application fee handling** — choose "Direct charges" with destination

### 8.2 Webhook Endpoints (Configure in Stripe Dashboard)

| Endpoint URL | Events | Secret Env Var |
|---|---|---|
| `https://your-api.com/api/webhooks/stripe` | `payment_intent.*`, `charge.refunded`, `refund.*` | `STRIPE_WEBHOOK_SECRET` |
| `https://your-api.com/api/webhooks/stripe-connect` | `account.updated`, `account.application.deauthorized`, `payout.paid`, `payout.failed`, `capability.updated` | `STRIPE_CONNECT_WEBHOOK_SECRET` |
| `https://your-api.com/api/offer-webhooks/stripe` | `checkout.session.completed`, `checkout.session.expired` | (existing offer webhook secret) |

### 8.3 Environment Variables Checklist

```bash
# Platform Stripe account
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...

# Webhook secrets (one per endpoint)
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_CONNECT_WEBHOOK_SECRET=whsec_...

# Connect platform
STRIPE_CONNECT_CLIENT_ID=ca_...

# Fee defaults
PLATFORM_FEE_PERCENT=4.0
PLATFORM_FEE_FIXED_CENTS=75

# Frontend
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_...
```

---

## Implementation Order & Dependencies

```
Phase 1 (Connect Onboarding Backend)
  ↓
Phase 2 (Fee Calculation & Destination Charges)     ← depends on Phase 1
  ↓
Phase 3 (Organizer UI)                              ← depends on Phase 1
Phase 4 (Attendee Checkout Enhancement)              ← depends on Phase 2
  ↓
Phase 5 (Admin Panel)                                ← depends on Phase 1 + 2
Phase 6 (Email Notifications)                        ← can run in parallel with 3-5
  ↓
Phase 7 (Testing)                                    ← after all phases
Phase 8 (Stripe Dashboard Config)                    ← before deployment
```

**Parallelizable**:
- Phase 3 + Phase 4 can run in parallel (after Phase 2)
- Phase 5 + Phase 6 can run in parallel
- Phase 8 is manual configuration, no code — can be done anytime

---

## Files That Will Be Created

| File | Phase |
|---|---|
| `event-lifecycle-service/app/services/payment/stripe_connect_service.py` | 1 |
| `event-lifecycle-service/app/graphql/connect_mutations.py` | 1 |
| `event-lifecycle-service/app/graphql/connect_queries.py` | 1 |
| `event-lifecycle-service/app/api/v1/endpoints/connect_webhooks.py` | 1 |
| `event-lifecycle-service/alembic/versions/p003_stripe_connect_enhancements.py` | 1 |
| `event-lifecycle-service/app/services/payment/fee_calculator.py` | 2 |
| `event-lifecycle-service/alembic/versions/p004_add_fee_fields_to_orders.py` | 2 |
| `globalconnect/src/app/(platform)/dashboard/settings/payments/page.tsx` | 3 |
| `globalconnect/src/app/(platform)/dashboard/settings/payments/return/page.tsx` | 3 |
| `globalconnect/src/app/(platform)/dashboard/settings/payments/refresh/page.tsx` | 3 |
| `globalconnect/src/graphql/connect.graphql.ts` | 3 |
| `globalconnect/src/hooks/use-stripe-connect.ts` | 3 |
| `globalconnect/src/app/(admin)/` (entire route group) | 5 |
| `event-lifecycle-service/app/graphql/admin_queries.py` | 5 |
| `event-lifecycle-service/app/graphql/admin_mutations.py` | 5 |
| `event-lifecycle-service/alembic/versions/p005_create_revenue_views.py` | 5 |
| `event-lifecycle-service/tests/test_fee_calculator.py` | 7 |
| `event-lifecycle-service/tests/test_stripe_connect_service.py` | 7 |
| `event-lifecycle-service/tests/test_payment_service_connect.py` | 7 |
| `event-lifecycle-service/tests/test_connect_webhooks.py` | 7 |

## Files That Will Be Modified

| File | Phase | Change |
|---|---|---|
| `event-lifecycle-service/app/core/config.py` | 1 | Add Connect env vars |
| `event-lifecycle-service/app/models/organization_payment_settings.py` | 1 | Add new columns |
| `event-lifecycle-service/app/graphql/schema.py` | 1, 2, 5 | Register new queries/mutations |
| `event-lifecycle-service/app/api/v1/api.py` | 1 | Register Connect webhook router |
| `event-lifecycle-service/app/services/payment/payment_service.py` | 1, 2 | Add gating + fee calc + Connect params |
| `event-lifecycle-service/app/services/payment/providers/stripe_provider.py` | 2 | Refund with application_fee handling |
| `event-lifecycle-service/app/services/payment/provider_factory.py` | 2 | Uncomment org-lookup TODO |
| `event-lifecycle-service/app/models/order.py` | 2 | Add subtotal_amount, fee_absorption columns |
| `event-lifecycle-service/app/graphql/payment_types.py` | 2 | Add fee fields to types |
| `event-lifecycle-service/app/schemas/payment.py` | 2 | Add fee fields to schemas |
| `globalconnect/src/components/features/checkout/ticket-selector.tsx` | 4 | Fee display in order summary |
| `globalconnect/src/components/features/checkout/payment-form.tsx` | 4 | Enhanced confirmation |
| `globalconnect/src/app/(platform)/dashboard/events/[eventId]/_components/ticket-management.tsx` | 3 | Connect Stripe banner |
| `globalconnect/src/types/payment.types.ts` | 3, 4 | Add fee-related types |
| `globalconnect/src/graphql/payments.graphql.ts` | 2, 4 | Add fee fields to queries |
| `globalconnect/.env.example` | 1 | Already has publishable key |
| `event-lifecycle-service/.env.example` | 1 | Add Connect vars |
| `user-and-org-service/prisma/schema.prisma` | 5 | Add isPlatformAdmin field |
