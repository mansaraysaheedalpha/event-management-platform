# Ticket Management System - Backend Requirements

> **Document Version:** 1.0
> **Last Updated:** December 2025
> **Status:** Implementation Ready
> **Prerequisite:** PAYMENT_PROVIDER_BACKEND.md must be implemented first

---

## Table of Contents

1. [Overview](#1-overview)
2. [Database Schema](#2-database-schema)
3. [GraphQL API](#3-graphql-api)
4. [Business Logic](#4-business-logic)
5. [Validation Rules](#5-validation-rules)
6. [Integration Points](#6-integration-points)

---

## 1. Overview

### 1.1 Purpose

This document specifies the backend requirements for the **Organizer Ticket Management** feature, enabling event organizers to:

- Create and manage ticket types (tiers) for their events
- Set pricing, capacity, and sales windows
- Create and manage promo/discount codes
- View ticket sales and revenue analytics
- Manage orders and process refunds

### 1.2 User Roles

| Role | Permissions |
|------|-------------|
| **Organizer** | Full CRUD on ticket types for their events |
| **Admin** | Full CRUD + can manage any organization's tickets |
| **Attendee** | Read-only (view available tickets, purchase) |

### 1.3 Relationship to Payment System

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TICKET MANAGEMENT FLOW                                │
└─────────────────────────────────────────────────────────────────────────────┘

  ORGANIZER SIDE                              ATTENDEE SIDE
  ──────────────                              ─────────────

  Create Event                                Browse Events
       │                                           │
       ▼                                           ▼
  Create Ticket Types ◄──────────────────────► View Available Tickets
  • Free Admission                                 │
  • Early Bird - $25                               ▼
  • General - $50                            Add to Cart
  • VIP - $150                                     │
       │                                           ▼
       ▼                                      Checkout (Payment)
  Create Promo Codes ◄──────────────────────► Apply Promo Code
       │                                           │
       ▼                                           ▼
  Monitor Sales                              Receive Tickets
       │                                           │
       ▼                                           ▼
  Process Refunds ◄──────────────────────────► Request Refund
```

---

## 2. Database Schema

### 2.1 `ticket_types` Table

Stores ticket tiers/types for events.

```sql
CREATE TABLE ticket_types (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationships
    event_id            UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    organization_id     UUID NOT NULL REFERENCES organizations(id),

    -- Basic Info
    name                VARCHAR(255) NOT NULL,
    description         TEXT,

    -- Pricing (in smallest currency unit - cents)
    price               INTEGER NOT NULL DEFAULT 0,
    currency            VARCHAR(3) NOT NULL DEFAULT 'USD',

    -- Inventory
    quantity_total      INTEGER,                    -- NULL = unlimited
    quantity_sold       INTEGER NOT NULL DEFAULT 0,
    quantity_reserved   INTEGER NOT NULL DEFAULT 0, -- Held in pending orders

    -- Per-Order Limits
    min_per_order       INTEGER NOT NULL DEFAULT 1,
    max_per_order       INTEGER NOT NULL DEFAULT 10,

    -- Sales Window
    sales_start_at      TIMESTAMP WITH TIME ZONE,   -- NULL = immediately available
    sales_end_at        TIMESTAMP WITH TIME ZONE,   -- NULL = until event starts

    -- Visibility & Status
    is_active           BOOLEAN NOT NULL DEFAULT true,
    is_hidden           BOOLEAN NOT NULL DEFAULT false,  -- Hidden but can be accessed via direct link
    sort_order          INTEGER NOT NULL DEFAULT 0,

    -- Metadata
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by          UUID REFERENCES users(id),

    -- Constraints
    CONSTRAINT check_price_positive CHECK (price >= 0),
    CONSTRAINT check_quantity_valid CHECK (
        quantity_sold >= 0 AND
        quantity_reserved >= 0 AND
        (quantity_total IS NULL OR quantity_sold + quantity_reserved <= quantity_total)
    ),
    CONSTRAINT check_min_max_order CHECK (min_per_order > 0 AND max_per_order >= min_per_order),
    CONSTRAINT check_sales_window CHECK (sales_end_at IS NULL OR sales_start_at IS NULL OR sales_end_at > sales_start_at)
);

-- Indexes
CREATE INDEX idx_ticket_types_event ON ticket_types(event_id);
CREATE INDEX idx_ticket_types_org ON ticket_types(organization_id);
CREATE INDEX idx_ticket_types_active ON ticket_types(event_id, is_active) WHERE is_active = true;
CREATE INDEX idx_ticket_types_sort ON ticket_types(event_id, sort_order);

-- Trigger to update updated_at
CREATE TRIGGER update_ticket_types_timestamp
    BEFORE UPDATE ON ticket_types
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### 2.2 `promo_codes` Table

Stores discount/promotional codes.

```sql
CREATE TABLE promo_codes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationships
    event_id            UUID REFERENCES events(id) ON DELETE CASCADE,  -- NULL = org-wide
    organization_id     UUID NOT NULL REFERENCES organizations(id),

    -- Code Details
    code                VARCHAR(50) NOT NULL,
    description         TEXT,

    -- Discount Configuration
    discount_type       VARCHAR(20) NOT NULL,  -- 'percentage', 'fixed'
    discount_value      INTEGER NOT NULL,       -- Percentage (0-100) or fixed amount in cents

    -- Applicable Ticket Types (NULL = all ticket types)
    applicable_ticket_type_ids  UUID[],

    -- Usage Limits
    max_uses            INTEGER,                -- NULL = unlimited
    max_uses_per_user   INTEGER DEFAULT 1,      -- Per user/email
    current_uses        INTEGER NOT NULL DEFAULT 0,

    -- Validity Period
    valid_from          TIMESTAMP WITH TIME ZONE,
    valid_until         TIMESTAMP WITH TIME ZONE,

    -- Minimum Requirements
    minimum_order_amount INTEGER,               -- Minimum order total in cents
    minimum_tickets     INTEGER DEFAULT 1,      -- Minimum tickets in order

    -- Status
    is_active           BOOLEAN NOT NULL DEFAULT true,

    -- Metadata
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by          UUID REFERENCES users(id),

    -- Constraints
    CONSTRAINT check_discount_type CHECK (discount_type IN ('percentage', 'fixed')),
    CONSTRAINT check_discount_value CHECK (
        (discount_type = 'percentage' AND discount_value > 0 AND discount_value <= 100) OR
        (discount_type = 'fixed' AND discount_value > 0)
    ),
    CONSTRAINT check_validity_window CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from),
    CONSTRAINT unique_code_per_event UNIQUE (organization_id, event_id, code)
);

-- Indexes
CREATE INDEX idx_promo_codes_event ON promo_codes(event_id);
CREATE INDEX idx_promo_codes_org ON promo_codes(organization_id);
CREATE INDEX idx_promo_codes_code ON promo_codes(organization_id, UPPER(code));
CREATE INDEX idx_promo_codes_active ON promo_codes(event_id, is_active) WHERE is_active = true;
```

### 2.3 `promo_code_usages` Table

Tracks promo code usage per user.

```sql
CREATE TABLE promo_code_usages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    promo_code_id       UUID NOT NULL REFERENCES promo_codes(id) ON DELETE CASCADE,
    order_id            UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    user_id             UUID REFERENCES users(id),
    guest_email         VARCHAR(255),
    discount_applied    INTEGER NOT NULL,       -- Actual discount amount in cents
    used_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Either user_id or guest_email must be set
    CONSTRAINT check_user_or_email CHECK (user_id IS NOT NULL OR guest_email IS NOT NULL)
);

-- Indexes
CREATE INDEX idx_promo_usage_code ON promo_code_usages(promo_code_id);
CREATE INDEX idx_promo_usage_order ON promo_code_usages(order_id);
CREATE INDEX idx_promo_usage_user ON promo_code_usages(promo_code_id, user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_promo_usage_email ON promo_code_usages(promo_code_id, LOWER(guest_email)) WHERE guest_email IS NOT NULL;
```

### 2.4 `tickets` Table (Generated Tickets)

Stores actual tickets issued to attendees after successful purchase.

```sql
CREATE TABLE tickets (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationships
    order_id            UUID NOT NULL REFERENCES orders(id),
    order_item_id       UUID NOT NULL REFERENCES order_items(id),
    ticket_type_id      UUID NOT NULL REFERENCES ticket_types(id),
    event_id            UUID NOT NULL REFERENCES events(id),

    -- Owner
    user_id             UUID REFERENCES users(id),
    attendee_email      VARCHAR(255) NOT NULL,
    attendee_name       VARCHAR(255) NOT NULL,

    -- Ticket Code (unique, scannable)
    ticket_code         VARCHAR(20) UNIQUE NOT NULL,  -- Format: TKT-XXXXXX-XX
    qr_code_data        TEXT,                         -- Encoded QR data

    -- Status
    status              VARCHAR(50) NOT NULL DEFAULT 'valid',
    -- Values: 'valid', 'checked_in', 'cancelled', 'transferred', 'refunded'

    -- Check-in
    checked_in_at       TIMESTAMP WITH TIME ZONE,
    checked_in_by       UUID REFERENCES users(id),    -- Staff who checked in
    check_in_location   VARCHAR(255),                 -- Entry point name

    -- Transfer (if transferred to another person)
    transferred_from_ticket_id  UUID REFERENCES tickets(id),
    transferred_at      TIMESTAMP WITH TIME ZONE,

    -- Metadata
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_tickets_order ON tickets(order_id);
CREATE INDEX idx_tickets_event ON tickets(event_id);
CREATE INDEX idx_tickets_user ON tickets(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_tickets_code ON tickets(ticket_code);
CREATE INDEX idx_tickets_status ON tickets(event_id, status);
CREATE INDEX idx_tickets_email ON tickets(event_id, LOWER(attendee_email));

-- Generate unique ticket code
CREATE OR REPLACE FUNCTION generate_ticket_code()
RETURNS TRIGGER AS $$
BEGIN
    NEW.ticket_code := 'TKT-' ||
                       UPPER(SUBSTRING(MD5(NEW.id::text || RANDOM()::text) FROM 1 FOR 6)) ||
                       '-' ||
                       UPPER(SUBSTRING(MD5(RANDOM()::text) FROM 1 FOR 2));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_ticket_code
    BEFORE INSERT ON tickets
    FOR EACH ROW
    WHEN (NEW.ticket_code IS NULL)
    EXECUTE FUNCTION generate_ticket_code();
```

---

## 3. GraphQL API

### 3.1 Types

```graphql
# ============================================
# Ticket Type Management
# ============================================

type TicketType {
  id: ID!
  eventId: ID!
  name: String!
  description: String

  # Pricing
  price: Money!

  # Inventory
  quantityTotal: Int           # null = unlimited
  quantityAvailable: Int       # computed: total - sold - reserved
  quantitySold: Int!
  quantityReserved: Int!

  # Limits
  minPerOrder: Int!
  maxPerOrder: Int!

  # Sales Window
  salesStartAt: DateTime
  salesEndAt: DateTime

  # Status
  isActive: Boolean!
  isHidden: Boolean!
  isOnSale: Boolean!           # Computed based on dates and availability
  sortOrder: Int!

  # Stats (for organizers)
  revenue: Money               # Total revenue from this ticket type

  createdAt: DateTime!
  updatedAt: DateTime!
}

type TicketTypeStats {
  ticketTypeId: ID!
  ticketTypeName: String!
  quantitySold: Int!
  quantityAvailable: Int
  revenue: Money!
  percentageSold: Float        # null if unlimited
}

# ============================================
# Promo Codes
# ============================================

enum DiscountType {
  PERCENTAGE
  FIXED
}

type PromoCode {
  id: ID!
  eventId: ID                  # null = organization-wide
  code: String!
  description: String

  # Discount
  discountType: DiscountType!
  discountValue: Int!          # Percentage (1-100) or cents
  discountFormatted: String!   # "20%" or "$10.00"

  # Applicable Tickets
  applicableTicketTypes: [TicketType!]  # null = all types

  # Usage
  maxUses: Int                 # null = unlimited
  maxUsesPerUser: Int!
  currentUses: Int!
  remainingUses: Int           # null if unlimited

  # Validity
  validFrom: DateTime
  validUntil: DateTime
  isCurrentlyValid: Boolean!   # Computed

  # Requirements
  minimumOrderAmount: Money
  minimumTickets: Int

  isActive: Boolean!
  createdAt: DateTime!
}

type PromoCodeValidation {
  isValid: Boolean!
  promoCode: PromoCode
  discountAmount: Money        # Calculated discount for current cart
  errorCode: String
  errorMessage: String
}

# ============================================
# Tickets (Issued)
# ============================================

enum TicketStatus {
  VALID
  CHECKED_IN
  CANCELLED
  TRANSFERRED
  REFUNDED
}

type Ticket {
  id: ID!
  ticketCode: String!
  ticketType: TicketType!
  event: Event!
  order: Order!

  # Attendee
  attendeeName: String!
  attendeeEmail: String!

  # Status
  status: TicketStatus!
  checkedInAt: DateTime
  checkedInBy: User
  checkInLocation: String

  # QR Code
  qrCodeUrl: String!           # URL to QR code image

  createdAt: DateTime!
}

# ============================================
# Event Ticket Summary (for organizers)
# ============================================

type EventTicketSummary {
  eventId: ID!
  totalTicketTypes: Int!
  totalCapacity: Int           # null if any ticket type is unlimited
  totalSold: Int!
  totalRevenue: Money!
  ticketTypeStats: [TicketTypeStats!]!

  # Sales by time period
  salesToday: Int!
  salesThisWeek: Int!
  salesThisMonth: Int!

  # Revenue by time period
  revenueToday: Money!
  revenueThisWeek: Money!
  revenueThisMonth: Money!
}

# ============================================
# Inputs
# ============================================

input CreateTicketTypeInput {
  eventId: ID!
  name: String!
  description: String
  price: Int!                  # In cents (0 for free)
  currency: String             # Default: USD
  quantityTotal: Int           # null = unlimited
  minPerOrder: Int             # Default: 1
  maxPerOrder: Int             # Default: 10
  salesStartAt: DateTime
  salesEndAt: DateTime
  isHidden: Boolean            # Default: false
  sortOrder: Int               # Default: 0
}

input UpdateTicketTypeInput {
  name: String
  description: String
  price: Int
  currency: String
  quantityTotal: Int
  minPerOrder: Int
  maxPerOrder: Int
  salesStartAt: DateTime
  salesEndAt: DateTime
  isActive: Boolean
  isHidden: Boolean
  sortOrder: Int
}

input CreatePromoCodeInput {
  eventId: ID                  # null = organization-wide
  code: String!
  description: String
  discountType: DiscountType!
  discountValue: Int!
  applicableTicketTypeIds: [ID!]
  maxUses: Int
  maxUsesPerUser: Int          # Default: 1
  validFrom: DateTime
  validUntil: DateTime
  minimumOrderAmount: Int      # In cents
  minimumTickets: Int
}

input UpdatePromoCodeInput {
  description: String
  discountType: DiscountType
  discountValue: Int
  applicableTicketTypeIds: [ID!]
  maxUses: Int
  maxUsesPerUser: Int
  validFrom: DateTime
  validUntil: DateTime
  minimumOrderAmount: Int
  minimumTickets: Int
  isActive: Boolean
}

input ReorderTicketTypesInput {
  eventId: ID!
  ticketTypeIds: [ID!]!        # Ordered list of IDs
}
```

### 3.2 Queries

```graphql
type Query {
  # ============================================
  # Ticket Types (Public - for purchase)
  # ============================================

  # Get available ticket types for an event (attendee view)
  eventTicketTypes(eventId: ID!): [TicketType!]!

  # ============================================
  # Ticket Types (Organizer)
  # ============================================

  # Get all ticket types including inactive (organizer view)
  eventTicketTypesAdmin(eventId: ID!): [TicketType!]!

  # Get single ticket type
  ticketType(id: ID!): TicketType

  # Get ticket summary for event
  eventTicketSummary(eventId: ID!): EventTicketSummary!

  # ============================================
  # Promo Codes (Organizer)
  # ============================================

  # List promo codes for event
  eventPromoCodes(eventId: ID!): [PromoCode!]!

  # List organization-wide promo codes
  organizationPromoCodes: [PromoCode!]!

  # Get single promo code
  promoCode(id: ID!): PromoCode

  # Validate promo code for cart (public)
  validatePromoCode(
    eventId: ID!
    code: String!
    cartItems: [CartItemInput!]!
  ): PromoCodeValidation!

  # ============================================
  # Tickets (Organizer)
  # ============================================

  # List all tickets for an event
  eventTickets(
    eventId: ID!
    status: TicketStatus
    search: String
    first: Int
    after: String
  ): TicketConnection!

  # Get ticket by code (for check-in)
  ticketByCode(eventId: ID!, ticketCode: String!): Ticket

  # ============================================
  # Tickets (Attendee)
  # ============================================

  # Get my tickets
  myTickets(eventId: ID): [Ticket!]!

  # Get single ticket
  ticket(id: ID!): Ticket
}
```

### 3.3 Mutations

```graphql
type Mutation {
  # ============================================
  # Ticket Type Management (Organizer)
  # ============================================

  # Create new ticket type
  createTicketType(input: CreateTicketTypeInput!): TicketType!

  # Update ticket type
  updateTicketType(id: ID!, input: UpdateTicketTypeInput!): TicketType!

  # Delete ticket type (only if no sales)
  deleteTicketType(id: ID!): Boolean!

  # Reorder ticket types
  reorderTicketTypes(input: ReorderTicketTypesInput!): [TicketType!]!

  # Duplicate ticket type
  duplicateTicketType(id: ID!): TicketType!

  # ============================================
  # Promo Code Management (Organizer)
  # ============================================

  # Create promo code
  createPromoCode(input: CreatePromoCodeInput!): PromoCode!

  # Update promo code
  updatePromoCode(id: ID!, input: UpdatePromoCodeInput!): PromoCode!

  # Delete promo code
  deletePromoCode(id: ID!): Boolean!

  # Deactivate promo code (soft disable)
  deactivatePromoCode(id: ID!): PromoCode!

  # ============================================
  # Ticket Check-in (Organizer/Staff)
  # ============================================

  # Check in a ticket
  checkInTicket(
    ticketCode: String!
    eventId: ID!
    location: String
  ): Ticket!

  # Reverse check-in (undo)
  reverseCheckIn(ticketId: ID!): Ticket!

  # ============================================
  # Ticket Management (Organizer)
  # ============================================

  # Cancel a ticket
  cancelTicket(ticketId: ID!, reason: String): Ticket!

  # Resend ticket email
  resendTicketEmail(ticketId: ID!): Boolean!

  # Transfer ticket to new attendee
  transferTicket(
    ticketId: ID!
    newAttendeeName: String!
    newAttendeeEmail: String!
  ): Ticket!
}
```

---

## 4. Business Logic

### 4.1 Ticket Availability Calculation

```typescript
/**
 * Calculate if a ticket type is currently available for purchase
 */
function isTicketOnSale(ticketType: TicketType): boolean {
  // Must be active
  if (!ticketType.isActive) return false;

  // Check sales window
  const now = new Date();

  if (ticketType.salesStartAt && now < ticketType.salesStartAt) {
    return false; // Sales haven't started
  }

  if (ticketType.salesEndAt && now > ticketType.salesEndAt) {
    return false; // Sales have ended
  }

  // Check inventory
  if (ticketType.quantityTotal !== null) {
    const available = ticketType.quantityTotal -
                      ticketType.quantitySold -
                      ticketType.quantityReserved;
    if (available <= 0) return false; // Sold out
  }

  return true;
}

/**
 * Calculate quantity available
 */
function getQuantityAvailable(ticketType: TicketType): number | null {
  if (ticketType.quantityTotal === null) return null; // Unlimited

  return Math.max(0,
    ticketType.quantityTotal -
    ticketType.quantitySold -
    ticketType.quantityReserved
  );
}
```

### 4.2 Promo Code Validation

```typescript
/**
 * Validate and calculate promo code discount
 */
async function validatePromoCode(
  code: string,
  eventId: string,
  cartItems: CartItem[],
  userId?: string,
  guestEmail?: string
): Promise<PromoCodeValidation> {

  // 1. Find promo code
  const promoCode = await db.promoCodes.findOne({
    where: {
      code: code.toUpperCase(),
      OR: [
        { eventId },
        { eventId: null, organizationId: event.organizationId }
      ]
    }
  });

  if (!promoCode) {
    return { isValid: false, errorCode: 'NOT_FOUND', errorMessage: 'Invalid promo code' };
  }

  // 2. Check if active
  if (!promoCode.isActive) {
    return { isValid: false, errorCode: 'INACTIVE', errorMessage: 'This code is no longer active' };
  }

  // 3. Check validity period
  const now = new Date();
  if (promoCode.validFrom && now < promoCode.validFrom) {
    return { isValid: false, errorCode: 'NOT_YET_VALID', errorMessage: 'This code is not yet valid' };
  }
  if (promoCode.validUntil && now > promoCode.validUntil) {
    return { isValid: false, errorCode: 'EXPIRED', errorMessage: 'This code has expired' };
  }

  // 4. Check usage limits
  if (promoCode.maxUses !== null && promoCode.currentUses >= promoCode.maxUses) {
    return { isValid: false, errorCode: 'MAX_USES', errorMessage: 'This code has reached its usage limit' };
  }

  // 5. Check per-user usage
  const userUsageCount = await db.promoCodeUsages.count({
    where: {
      promoCodeId: promoCode.id,
      OR: [
        { userId },
        { guestEmail: guestEmail?.toLowerCase() }
      ]
    }
  });

  if (userUsageCount >= promoCode.maxUsesPerUser) {
    return { isValid: false, errorCode: 'USER_LIMIT', errorMessage: 'You have already used this code' };
  }

  // 6. Check applicable ticket types
  const applicableItems = cartItems.filter(item => {
    if (!promoCode.applicableTicketTypeIds || promoCode.applicableTicketTypeIds.length === 0) {
      return true; // Applies to all
    }
    return promoCode.applicableTicketTypeIds.includes(item.ticketTypeId);
  });

  if (applicableItems.length === 0) {
    return {
      isValid: false,
      errorCode: 'NOT_APPLICABLE',
      errorMessage: 'This code does not apply to your selected tickets'
    };
  }

  // 7. Calculate discount
  const applicableSubtotal = applicableItems.reduce((sum, item) =>
    sum + (item.price * item.quantity), 0
  );

  let discountAmount: number;
  if (promoCode.discountType === 'percentage') {
    discountAmount = Math.floor(applicableSubtotal * (promoCode.discountValue / 100));
  } else {
    discountAmount = Math.min(promoCode.discountValue, applicableSubtotal);
  }

  // 8. Check minimum requirements
  const totalQuantity = cartItems.reduce((sum, item) => sum + item.quantity, 0);
  const cartTotal = cartItems.reduce((sum, item) => sum + (item.price * item.quantity), 0);

  if (promoCode.minimumTickets && totalQuantity < promoCode.minimumTickets) {
    return {
      isValid: false,
      errorCode: 'MIN_TICKETS',
      errorMessage: `Minimum ${promoCode.minimumTickets} tickets required`
    };
  }

  if (promoCode.minimumOrderAmount && cartTotal < promoCode.minimumOrderAmount) {
    return {
      isValid: false,
      errorCode: 'MIN_AMOUNT',
      errorMessage: `Minimum order of ${formatMoney(promoCode.minimumOrderAmount)} required`
    };
  }

  return {
    isValid: true,
    promoCode,
    discountAmount: { amount: discountAmount, currency: 'USD' }
  };
}
```

### 4.3 Ticket Generation (After Payment)

```typescript
/**
 * Generate tickets after successful payment
 * Called by webhook handler after payment_intent.succeeded
 */
async function generateTicketsForOrder(orderId: string): Promise<Ticket[]> {
  const order = await db.orders.findUnique({
    where: { id: orderId },
    include: { items: true }
  });

  if (!order || order.status !== 'COMPLETED') {
    throw new Error('Invalid order state');
  }

  const tickets: Ticket[] = [];

  for (const item of order.items) {
    // Generate one ticket per quantity
    for (let i = 0; i < item.quantity; i++) {
      const ticket = await db.tickets.create({
        data: {
          orderId: order.id,
          orderItemId: item.id,
          ticketTypeId: item.ticketTypeId,
          eventId: order.eventId,
          userId: order.userId,
          attendeeEmail: order.customerEmail,
          attendeeName: order.customerName,
          status: 'VALID',
        }
      });

      tickets.push(ticket);
    }

    // Update sold quantity
    await db.ticketTypes.update({
      where: { id: item.ticketTypeId },
      data: {
        quantitySold: { increment: item.quantity },
        quantityReserved: { decrement: item.quantity }
      }
    });
  }

  // Send confirmation email with tickets
  await sendTicketConfirmationEmail(order, tickets);

  return tickets;
}
```

### 4.4 Inventory Reservation

```typescript
/**
 * Reserve inventory when checkout starts
 * Prevents overselling during checkout
 */
async function reserveInventory(
  items: Array<{ ticketTypeId: string; quantity: number }>
): Promise<void> {
  await db.transaction(async (tx) => {
    for (const item of items) {
      const ticketType = await tx.ticketTypes.findUnique({
        where: { id: item.ticketTypeId },
        select: { quantityTotal: true, quantitySold: true, quantityReserved: true }
      });

      if (ticketType.quantityTotal !== null) {
        const available = ticketType.quantityTotal -
                          ticketType.quantitySold -
                          ticketType.quantityReserved;

        if (available < item.quantity) {
          throw new Error(`Insufficient inventory for ticket type ${item.ticketTypeId}`);
        }
      }

      await tx.ticketTypes.update({
        where: { id: item.ticketTypeId },
        data: { quantityReserved: { increment: item.quantity } }
      });
    }
  });
}

/**
 * Release reservation when order expires or is cancelled
 */
async function releaseReservation(orderId: string): Promise<void> {
  const order = await db.orders.findUnique({
    where: { id: orderId },
    include: { items: true }
  });

  for (const item of order.items) {
    await db.ticketTypes.update({
      where: { id: item.ticketTypeId },
      data: { quantityReserved: { decrement: item.quantity } }
    });
  }
}
```

---

## 5. Validation Rules

### 5.1 Ticket Type Validation

| Field | Rules |
|-------|-------|
| `name` | Required, 1-255 chars |
| `price` | Required, >= 0 |
| `currency` | Required, valid ISO 4217 code |
| `quantityTotal` | If set, must be >= quantitySold |
| `minPerOrder` | Required, >= 1 |
| `maxPerOrder` | Required, >= minPerOrder, <= quantityTotal (if set) |
| `salesStartAt` | If salesEndAt set, must be before it |
| `salesEndAt` | If salesStartAt set, must be after it |

### 5.2 Promo Code Validation

| Field | Rules |
|-------|-------|
| `code` | Required, 3-50 chars, alphanumeric + dashes, unique per event/org |
| `discountType` | Required, must be 'percentage' or 'fixed' |
| `discountValue` | Required, > 0; if percentage, <= 100 |
| `maxUsesPerUser` | Required, >= 1 |
| `validFrom` | If validUntil set, must be before it |
| `validUntil` | If validFrom set, must be after it |

### 5.3 Delete Restrictions

| Entity | Can Delete When |
|--------|----------------|
| Ticket Type | No tickets sold (quantitySold = 0) |
| Promo Code | Can always delete (usage history preserved) |
| Ticket | Never (can only cancel/refund) |

---

## 6. Integration Points

### 6.1 Event Lifecycle

```yaml
When Event Created:
  - No ticket types created by default
  - Organizer must add at least one ticket type before publishing
  - Free events can have a single "Free Admission" ticket type

When Event Published:
  - Must have at least one active ticket type
  - Ticket sales begin based on salesStartAt or immediately

When Event Starts:
  - Default: Stop ticket sales (salesEndAt = event.startDate)
  - Organizer can override to allow door sales

When Event Ends:
  - All pending orders expire
  - Reserved inventory released
  - Final sales reports generated

When Event Archived:
  - Ticket types preserved for records
  - No new purchases allowed
  - Existing tickets remain valid for check-in
```

### 6.2 Order/Payment Integration

```yaml
Checkout Flow:
  1. User selects tickets → Reserve inventory
  2. User enters details → Create order (PENDING)
  3. User completes payment → Stripe webhook
  4. Webhook received →
     - Update order (COMPLETED)
     - Generate tickets
     - Convert reserved → sold
     - Send confirmation email

Order Expiration:
  - Default: 30 minutes
  - On expiry → Release reserved inventory
  - Order status → EXPIRED

Refund:
  - Cancel tickets
  - Decrement quantitySold
  - Process refund via payment provider
```

### 6.3 Frontend Integration Points

| Location | Integration |
|----------|-------------|
| Event Detail Page (Organizer) | Add "Tickets" tab with ticket type list |
| Event Details Card | Show real ticket sales stats |
| Event Header | Add "Manage Tickets" quick action |
| Create Event Modal | Optional: Add basic ticket type |
| Orders Tab (new) | View orders, process refunds |

---

## Appendix: Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `TICKET_TYPE_NOT_FOUND` | 404 | Ticket type doesn't exist |
| `TICKET_TYPE_SOLD_OUT` | 400 | No inventory available |
| `SALES_NOT_STARTED` | 400 | Sales window hasn't opened |
| `SALES_ENDED` | 400 | Sales window has closed |
| `MIN_QUANTITY_NOT_MET` | 400 | Below minimum per order |
| `MAX_QUANTITY_EXCEEDED` | 400 | Above maximum per order |
| `PROMO_CODE_NOT_FOUND` | 404 | Invalid promo code |
| `PROMO_CODE_EXPIRED` | 400 | Code past validity |
| `PROMO_CODE_MAX_USES` | 400 | Code usage limit reached |
| `PROMO_CODE_USER_LIMIT` | 400 | User already used code |
| `CANNOT_DELETE_WITH_SALES` | 400 | Ticket type has sales |
| `TICKET_ALREADY_CHECKED_IN` | 400 | Duplicate check-in attempt |
| `TICKET_CANCELLED` | 400 | Ticket is not valid |

---

*End of Document*
