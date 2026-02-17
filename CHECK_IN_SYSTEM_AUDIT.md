# Check-In System Deep Audit Report

**Date:** February 15, 2026
**Auditor:** Platform Architecture Review
**Scope:** Complete check-in flow — backend, frontend, real-time, database
**Verdict:** NOT PRODUCTION-READY — Critical security flaws, missing core features

---

## TABLE OF CONTENTS

1. [Current System Map](#1-current-system-map)
2. [Bug List](#2-bug-list)
3. [Production Readiness Scores](#3-production-readiness-scores)
4. [African Market Assessment](#4-african-market-assessment)
5. [Recommended Architecture](#5-recommended-architecture)
6. [Implementation Prompts](#6-implementation-prompts)

---

## 1. CURRENT SYSTEM MAP

### 1.1 Architecture Overview

The check-in system spans three services and a frontend:

```
┌─────────────────┐     GraphQL      ┌──────────────────────────┐
│   globalconnect  │ ───────────────> │  event-lifecycle-service  │
│   (Next.js PWA)  │                  │  (FastAPI + PostgreSQL)   │
└────────┬────────┘                  └──────────────────────────┘
         │                                       │
         │ Socket.IO                             │ HTTP (internal)
         ▼                                       ▼
┌──────────────────────────┐          ┌──────────────────┐
│   real-time-service       │ ──────> │  Kafka / Redis    │
│   (NestJS + Prisma)       │          └──────────────────┘
└──────────────────────────┘
```

### 1.2 Backend Files (event-lifecycle-service)

| File | Purpose |
|------|---------|
| [ticket.py](event-lifecycle-service/app/models/ticket.py) | Ticket model — status, QR data, check-in fields |
| [ticket_type.py](event-lifecycle-service/app/models/ticket_type.py) | Ticket tiers — pricing, capacity, sales windows |
| [registration.py](event-lifecycle-service/app/models/registration.py) | Free event registration with ticket codes |
| [session_rsvp.py](event-lifecycle-service/app/models/session_rsvp.py) | Session-level RSVP with capacity enforcement |
| [session_capacity.py](event-lifecycle-service/app/models/session_capacity.py) | Dynamic session capacity tracking |
| [virtual_attendance.py](event-lifecycle-service/app/models/virtual_attendance.py) | Virtual session join/leave tracking |
| [order.py](event-lifecycle-service/app/models/order.py) | Purchase orders |
| [order_item.py](event-lifecycle-service/app/models/order_item.py) | Order line items |
| [ticket_crud.py](event-lifecycle-service/app/crud/ticket_crud.py) | Ticket CRUD + check-in operation |
| [crud_registration.py](event-lifecycle-service/app/crud/crud_registration.py) | Registration CRUD + ticket code generation |
| [crud_session_rsvp.py](event-lifecycle-service/app/crud/crud_session_rsvp.py) | RSVP with atomic capacity enforcement (SELECT FOR UPDATE) |
| [crud_session_capacity.py](event-lifecycle-service/app/crud/crud_session_capacity.py) | Capacity increment/decrement |
| [ticket_service.py](event-lifecycle-service/app/services/ticket_management/ticket_service.py) | Business logic orchestration |
| [ticket_mutations.py](event-lifecycle-service/app/graphql/ticket_mutations.py) | GraphQL check-in + ticket management mutations |
| [ticket_queries.py](event-lifecycle-service/app/graphql/ticket_queries.py) | GraphQL ticket queries + stats |
| [rsvp_mutations.py](event-lifecycle-service/app/graphql/rsvp_mutations.py) | Session RSVP with capacity locking |
| [ticket_management.py](event-lifecycle-service/app/schemas/ticket_management.py) | Pydantic schemas + validation |
| [t001_create_ticket_management_tables.py](event-lifecycle-service/alembic/versions/t001_create_ticket_management_tables.py) | DB migration |

### 1.3 Frontend Files (globalconnect)

| File | Purpose |
|------|---------|
| [ticket-check-in.tsx](globalconnect/src/app/(platform)/dashboard/events/[eventId]/_components/ticket-check-in.tsx) | Organizer check-in tool — manual code entry |
| [tickets/page.tsx](globalconnect/src/app/(attendee)/attendee/tickets/page.tsx) | Attendee ticket display with QR codes |
| [ticket-management.tsx](globalconnect/src/app/(platform)/dashboard/events/[eventId]/_components/ticket-management.tsx) | Ticket type CRUD + metrics dashboard |
| [SessionRsvpButton.tsx](globalconnect/src/components/features/sessions/SessionRsvpButton.tsx) | Session RSVP with capacity display |
| [use-ticket-validation.ts](globalconnect/src/hooks/use-ticket-validation.ts) | Ticket validation hook |
| [use-ticket-metrics.ts](globalconnect/src/hooks/use-ticket-metrics.ts) | Real-time metrics via Socket.IO |
| [payments.graphql.ts](globalconnect/src/graphql/payments.graphql.ts) | CHECK_IN_TICKET_MUTATION |
| [attendee.graphql.ts](globalconnect/src/graphql/attendee.graphql.ts) | Registration + RSVP queries |
| [offline-storage.ts](globalconnect/src/lib/offline-storage.ts) | IndexedDB offline storage |
| [use-offline-query.ts](globalconnect/src/hooks/use-offline-query.ts) | Offline-first Apollo wrapper |

### 1.4 Real-Time Service Files (real-time-service)

| File | Purpose |
|------|---------|
| [validation.gateway.ts](real-time-service/src/live/validation/validation.gateway.ts) | WebSocket ticket validation handler |
| [validation.service.ts](real-time-service/src/live/validation/validation.service.ts) | Validation logic with idempotency |
| [validate-ticket.dto.ts](real-time-service/src/live/validation/dto/validate-ticket.dto.ts) | Validation input DTO |
| [dashboard.service.ts](real-time-service/src/live/dashboard/dashboard.service.ts) | Live check-in feed + analytics |
| [dashboard.controller.ts](real-time-service/src/live/dashboard/dashboard.controller.ts) | Dashboard REST + Kafka handlers |
| [app.gateway.ts](real-time-service/src/app.gateway.ts) | Main WebSocket gateway — dashboard broadcasts |
| [tickets.gateway.ts](real-time-service/src/tickets/tickets.gateway.ts) | Ticket metrics WebSocket |
| [ws-throttler.guard.ts](real-time-service/src/common/guards/ws-throttler.guard.ts) | WebSocket rate limiting |
| [jwt-auth.guard.ts](real-time-service/src/common/guards/jwt-auth.guard.ts) | JWT authentication guard |
| [internal-api-key.guard.ts](real-time-service/src/common/guards/internal-api-key.guard.ts) | Internal API key guard |
| [idempotency.service.ts](real-time-service/src/shared/services/idempotency.service.ts) | Redis-based idempotency |

### 1.5 Database Schema

**7 tables** involved in check-in:

```sql
-- Core check-in tables
tickets           -- Issued tickets with QR data, check-in status
registrations     -- Free event registrations with ticket codes
session_rsvps     -- Session-level RSVPs with capacity
session_capacity  -- Per-session max/current attendance

-- Supporting tables
orders            -- Purchase records
order_items       -- Order line items
virtual_attendance -- Virtual session tracking
```

**Key constraints:**
- `tickets.ticket_code` — UNIQUE
- `session_rsvps(session_id, user_id)` — UNIQUE
- `session_capacity.current_attendance <= maximum_capacity` — CHECK
- `session_capacity.current_attendance >= 0` — CHECK

**Indexes (20+):**
- `tickets(ticket_code)`, `tickets(event_id, status)`, `tickets(event_id)`, `tickets(user_id)`, `tickets(order_id)`
- `registrations(event_id, status, is_archived)`, `registrations(user_id, is_archived, status)`
- `session_rsvps(session_id)`, `session_rsvps(user_id)`, `session_rsvps(event_id)`

### 1.6 Check-In Journey Map

**Current flow (paid tickets):**
```
1. Attendee purchases ticket → Order created → Payment processed
2. generate_tickets_for_order() creates Ticket records with unique codes + QR data
3. Attendee views /attendee/tickets → QR code displayed (using ticketCode only!)
4. At event: Organizer opens /dashboard/events/[id] → ticket-check-in component
5. Organizer manually types ticket code (XXX-XXX-XX format)
6. GraphQL checkInTicket mutation → ticket_service.check_in_ticket()
7. ticket_crud.check_in() → status='checked_in', records timestamp + staff ID + location
8. Success/failure toast shown to organizer
```

**Current flow (free registrations):**
```
1. Attendee registers → Registration created with generated ticket_code (XXX-XXX-XXX)
2. Attendee views registration → ticket_code displayed
3. At event: Manual verification of registration code
4. Registration status → 'checked_in'
```

**Current flow (session RSVP):**
```
1. Attendee RSVPs to session → Atomic capacity check with SELECT FOR UPDATE
2. SessionCapacity.current_attendance incremented
3. On cancel → Atomic decrement + auto-offer to next waitlist entry
```

---

## 2. BUG LIST

### CRITICAL (Must fix before any production event)

#### C1. QR Codes Are NOT Cryptographically Signed — Forgeable
**File:** [ticket.py:92-98](event-lifecycle-service/app/models/ticket.py#L92-L98)
```python
def _generate_qr_data(self) -> str:
    data = f"{self.id}|{self.ticket_code}|{self.event_id}"
    hash_part = hashlib.sha256(data.encode()).hexdigest()[:8]
    return f"{data}|{hash_part}"
```
**Problem:** The "hash" is just `SHA256(plaintext_data)[:8]` — a checksum of the data itself, NOT a signature with a secret key. Anyone who knows the format (`{id}|{code}|{event_id}`) can compute a valid hash. This means:
- QR codes can be forged by anyone who knows the format
- Only 8 hex chars (32 bits) — trivially brute-forceable even without knowing the format
- No server-side secret involved at all
- No expiration — QR codes are valid forever
**Impact:** Complete ticket forgery possible. Attackers can generate unlimited fake tickets.
**Fix:** Replace with JWT-signed QR codes using a server-side secret key. Include `iat` and `exp` claims.

#### C2. Frontend QR Code Ignores Backend Security — Exposes Raw Ticket Code
**File:** [tickets/page.tsx:~120](globalconnect/src/app/(attendee)/attendee/tickets/page.tsx)
```tsx
<QRCodeSVG value={registration.ticketCode} size={80} />
```
**Problem:** The frontend generates QR codes from just the plain `ticketCode` string, completely ignoring the backend's `qr_code_data` field which at least includes an integrity hash. The QR code is literally just the human-readable code — scanning it reveals the code instantly.
**Impact:** Screenshots of QR codes = instant ticket theft. No additional verification layer.
**Fix:** Use the backend's `qr_code_data` field (or better, a signed JWT) as the QR value.

#### C3. No Authorization Check on Check-In Mutation — Any User Can Check In Anyone
**File:** [ticket_mutations.py:267-288](event-lifecycle-service/app/graphql/ticket_mutations.py#L267-L288)
```python
async def checkInTicket(self, info: Info, input: CheckInTicketInput) -> TicketGQLType:
    db = info.context.db
    user = info.context.user
    staff_user_id = user.get("sub") if user else "unknown"
    # NO CHECK: Is this user an organizer/staff for this event?
    ticket = ticket_management_service.check_in_ticket(...)
```
**Problem:** The mutation only checks if the user is authenticated (has a JWT), NOT if they are an organizer or staff member for the event. Any logged-in attendee could call this mutation and check in any ticket.
**Impact:** Complete authorization bypass. Attendees could check themselves in without being physically present, or check in tickets they don't own.
**Fix:** Add organization membership + event ownership verification before allowing check-in.

#### C4. Race Condition in Check-In — No Database Lock
**File:** [ticket_crud.py:169-192](event-lifecycle-service/app/crud/ticket_crud.py#L169-L192)
```python
def check_in(self, db, ticket_id, checked_in_by, location=None):
    ticket = self.get(db, ticket_id)  # READ without lock
    if not ticket.can_check_in:       # CHECK status
        raise ValueError(...)
    ticket.status = "checked_in"      # UPDATE
    db.commit()
```
**Problem:** The `get` → `check` → `update` pattern has no `SELECT FOR UPDATE`. Two staff members scanning the same ticket simultaneously can both see `status='valid'` and both proceed. Contrast with `crud_session_rsvp.py` which correctly uses `with_for_update()`.
**Impact:** Duplicate check-ins for the same ticket. Corrupted attendance counts. The session RSVP code does this correctly, proving the team knows how — this was just missed for ticket check-in.
**Fix:** Add `with_for_update()` to the ticket query, or use an atomic UPDATE with WHERE clause.

#### C5. No Rate Limiting on GraphQL Check-In Mutation
**File:** [ticket_mutations.py:267](event-lifecycle-service/app/graphql/ticket_mutations.py#L267)
**Problem:** The `checkInTicket` GraphQL mutation has no rate limiting. The WebSocket validation path has throttling via `WsThrottlerGuard`, but the GraphQL path (which the frontend actually uses!) has none.
**Impact:** Brute-force ticket code guessing. An attacker could try all `36^8` (~2.8 trillion) possible codes. At even 100 requests/second, the `TKT-XXXXXX-XX` format with only 8 hex chars (16^8 = 4.3 billion) is vulnerable.
**Fix:** Add rate limiting to the GraphQL resolver (e.g., 30 check-ins/minute per user).

### HIGH (Must fix before scaling)

#### H1. No Ticket/QR Code Expiration
**Files:** [ticket.py](event-lifecycle-service/app/models/ticket.py), [ticket_crud.py](event-lifecycle-service/app/crud/ticket_crud.py)
**Problem:** Tickets never expire. Once generated, a QR code is valid forever — even after the event ends. No `expires_at` field exists.
**Impact:** Old tickets could be reused at future events if ticket codes collide or if the system is misconfigured.
**Fix:** Add `expires_at` to tickets, default to event end date + 24 hours.

#### H2. No Replay Attack Prevention
**Problem:** A screenshot of someone's QR code works indefinitely. There's no one-time-use mechanism, no device binding, no temporal token rotation.
**Impact:** Ticket sharing/scalping impossible to prevent. One attendee could share their QR code image with multiple people.
**Fix:** Implement rotating QR tokens (TOTP-like) that change every 30 seconds, or device-bound verification.

#### H3. staff_user_id Falls Back to "unknown"
**File:** [ticket_mutations.py:276](event-lifecycle-service/app/graphql/ticket_mutations.py#L276)
```python
staff_user_id = user.get("sub") if user else "unknown"
```
**Problem:** If `user` is set but `user.get("sub")` returns None, the staff_user_id will be None (not "unknown"). If `user` is entirely None, the fallback is "unknown". Either way, the audit trail is broken.
**Impact:** Cannot determine which staff member performed a check-in. Audit trail compromised.
**Fix:** Require valid staff_user_id; reject check-in if not authenticated.

#### H4. No Camera-Based QR Scanning — Manual Entry Only
**File:** [ticket-check-in.tsx](globalconnect/src/app/(platform)/dashboard/events/[eventId]/_components/ticket-check-in.tsx)
**Problem:** The organizer check-in tool only supports manual ticket code entry. There is NO camera-based QR scanner. Staff must physically read the code from the attendee's phone and type it character by character.
**Impact:** Check-in takes 15-30 seconds per person instead of 1-2 seconds. At a 5,000-person event with 4 gates, this means ~30+ minutes of queue time vs ~5 minutes with scanning. Completely unacceptable for production.
**Fix:** Integrate html5-qrcode or @aspect-build/aspect-qr-scanner for camera-based scanning.

#### H5. No Offline Check-In for Organizers
**Files:** [ticket-check-in.tsx](globalconnect/src/app/(platform)/dashboard/events/[eventId]/_components/ticket-check-in.tsx), [use-ticket-validation.ts](globalconnect/src/hooks/use-ticket-validation.ts)
**Problem:** Every check-in requires a network round-trip. If the internet drops (common at crowded African venues), check-in stops entirely. The attendee ticket page has offline support via `useOfflineQuery`, but the organizer check-in tool has NONE.
**Impact:** Event check-in halts when network drops. This is a dealbreaker for the African market where MTN/Airtel networks routinely drop at crowded venues.
**Fix:** Implement offline-first PWA scanner that pre-caches attendee list and validates locally.

#### H6. Missing Event Ownership Verification in Real-Time Validation
**File:** [validation.gateway.ts](real-time-service/src/live/validation/validation.gateway.ts)
**Problem:** The WebSocket validation gateway checks `event:validate_tickets` permission but doesn't verify the user has access to the specific event. A staff member at Event A could validate tickets for Event B.
**Impact:** Cross-event ticket validation. Staff could check in tickets for events they don't manage.
**Fix:** Verify user's organization owns the event before allowing validation.

#### H7. PII Exposed in Live Dashboard Check-In Feed
**File:** [dashboard.service.ts](real-time-service/src/live/dashboard/dashboard.service.ts)
**Problem:** The live check-in feed contains attendee names and user IDs. This data is broadcast to all clients in the dashboard room without PII filtering.
**Impact:** Privacy violation. Attendee personal data visible to anyone with dashboard access.
**Fix:** Show only initials or anonymized identifiers in the feed. Full names only in admin-level views.

#### H8. resendTicketEmail Mutation Is a Stub
**File:** [ticket_mutations.py:332-343](event-lifecycle-service/app/graphql/ticket_mutations.py#L332-L343)
```python
async def resendTicketEmail(self, info, ticketId):
    # Email sending will be handled by notification service integration
    # For now, return True to indicate the request was accepted
    return True
```
**Problem:** This mutation always returns `True` but never actually sends an email. If the frontend calls this, users will think the email was sent.
**Impact:** Users waiting for ticket emails that will never arrive. Loss of trust.
**Fix:** Integrate with email-consumer-worker via Kafka, or add a clear "not yet available" error.

### MEDIUM

#### M1. GraphQL Check-In Mutation Lacks Idempotency Key
**File:** [use-ticket-validation.ts](globalconnect/src/hooks/use-ticket-validation.ts)
**Problem:** The GraphQL mutation path doesn't use idempotency keys. The WebSocket path does (via `IdempotencyService`), creating an inconsistency. Double-clicking the submit button sends two mutations.
**Fix:** Add `idempotencyKey: UUID` to `CheckInTicketInput`.

#### M2. Error Messages Leak Backend Details to Frontend
**File:** [use-ticket-validation.ts:~65](globalconnect/src/hooks/use-ticket-validation.ts)
```typescript
const errorMessage = err instanceof Error ? err.message : "Failed to validate ticket";
```
**Problem:** Raw `err.message` can contain database errors, JWT errors, or internal paths.
**Fix:** Map errors to user-friendly codes (TICKET_NOT_FOUND, NOT_AUTHORIZED, etc.).

#### M3. Check-In History Lost on Page Reload
**File:** [ticket-check-in.tsx](globalconnect/src/app/(platform)/dashboard/events/[eventId]/_components/ticket-check-in.tsx)
**Problem:** Check-in history stored only in React state. Page reload loses all history.
**Fix:** Persist to localStorage or IndexedDB.

#### M4. QR Code Size Too Small for Reliable Scanning
**File:** [tickets/page.tsx](globalconnect/src/app/(attendee)/attendee/tickets/page.tsx)
```tsx
<QRCodeSVG value={registration.ticketCode} size={80} />
```
**Problem:** 80px QR code is too small for many cameras, especially low-end phones with poor cameras.
**Fix:** Default to 200px minimum with tap-to-enlarge to fullscreen.

#### M5. Revenue Calculation Uses Approximation
**File:** [ticket_service.py:536-538](event-lifecycle-service/app/services/ticket_management/ticket_service.py#L536-L538)
```python
avg_price = total_revenue // total_sold if total_sold > 0 else 0
revenue_today = avg_price * sales_stats["sales_today"]
```
**Problem:** Per-period revenue is estimated from average price × count, not actual revenue.
**Fix:** Query actual ticket prices with time-based aggregation.

#### M6. WebSocket `ping` Events Bypass Throttling
**File:** [ws-throttler.guard.ts](real-time-service/src/common/guards/ws-throttler.guard.ts)
**Problem:** Ping events bypass rate limiting. Could be exploited for reconnaissance.
**Fix:** Apply lighter throttling (e.g., 1000/min) even on pings.

#### M7. No Bulk Check-In Option
**Problem:** No way to check in multiple attendees at once (e.g., a bus of delegates arriving together).
**Fix:** Add bulk check-in endpoint accepting array of ticket codes.

#### M8. Query String JWT Token Exposure
**File:** [auth.utils.ts](real-time-service/src/common/utils/auth.utils.ts)
**Problem:** JWT fallback via query string exposes tokens in URLs, logs, and browser history.
**Fix:** Remove query string fallback; use only auth header.

#### M9. No Ticket Transfer UI
**Problem:** Backend supports `transferTicket` mutation, but frontend has no UI for it.
**Fix:** Add transfer flow in attendee ticket view.

### LOW

#### L1. Case-Sensitive Internal API Key Header Matching
**File:** [internal-api-key.guard.ts](real-time-service/src/common/guards/internal-api-key.guard.ts)

#### L2. No Screen Reader Support for QR Codes
**File:** [tickets/page.tsx](globalconnect/src/app/(attendee)/attendee/tickets/page.tsx)

#### L3. ticketCode Has No Length Validation in WebSocket DTO
**File:** [validate-ticket.dto.ts](real-time-service/src/live/validation/dto/validate-ticket.dto.ts)

#### L4. No Search/Filter in Check-In History
**File:** [ticket-check-in.tsx](globalconnect/src/app/(platform)/dashboard/events/[eventId]/_components/ticket-check-in.tsx)

#### L5. Dashboard totalAttendees Parameter Has No Bounds Validation
**File:** [dashboard.controller.ts](real-time-service/src/live/dashboard/dashboard.controller.ts)

---

## 3. PRODUCTION READINESS SCORES

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| **Security** | **2/10** | QR codes forgeable, no authorization on check-in, no rate limiting, no replay prevention. Fundamentally broken. |
| **Reliability** | **4/10** | Race condition on check-in, no offline support for organizers, good session RSVP locking. Mixed. |
| **Performance** | **5/10** | Good indexing, Redis caching for dashboard, 5s broadcast cycles. But no QR scanning means 15-30s per check-in vs 1-2s target. |
| **UX (Organizer)** | **3/10** | Manual code entry only, no QR scanner, no bulk check-in, history lost on reload, no offline mode. Barely functional. |
| **UX (Attendee)** | **5/10** | QR code displayed but tiny (80px), offline ticket viewing works, no zoom, no ticket transfer UI. |
| **Data Integrity** | **5/10** | Timestamps logged, staff ID recorded (but can be "unknown"), race condition risks double-counting, no session-level check-in tracking for paid tickets. |
| **Code Quality** | **6/10** | Good patterns in RSVP (SELECT FOR UPDATE), clean separation of concerns, but inconsistent — ticket check-in doesn't follow the same patterns. TypeScript/Python type safety is decent. |

### **Overall: 4.3/10 — NOT Production Ready**

The system has a solid foundation (models, RSVP capacity enforcement, offline attendee views) but the actual check-in flow has critical security holes and missing features that make it unsuitable for production events.

---

## 4. AFRICAN MARKET ASSESSMENT

### 4.1 Connectivity (FAIL)
- **Organizer check-in requires internet for every scan.** At a 2,000-person event at Kigali Convention Centre or Eko Hotels Lagos, MTN/Airtel networks WILL drop when 2,000+ phones connect to nearby towers.
- Attendee ticket viewing has offline support (IndexedDB) — good.
- **Verdict:** Organizer-side offline check-in is a HARD REQUIREMENT for Africa.

### 4.2 Device Diversity (FAIL)
- No camera-based QR scanning at all. Staff MUST manually type codes.
- When QR scanning is added, it must handle poor-quality cameras on Tecno Spark, Infinix Hot, and itel phones (the most common phones in Africa, all with budget cameras).
- QR code at 80px is too small for low-res cameras.
- **Verdict:** Camera scanning with robust low-quality camera support is essential.

### 4.3 Cost Sensitivity (PARTIAL PASS)
- No dedicated scanning hardware required — phone-based.
- But without camera scanning, staff speed is terrible, requiring MORE staff.
- **Verdict:** Camera scanning eliminates need for extra staff.

### 4.4 Power/Battery (NOT ASSESSED)
- No battery optimization considerations found.
- 5-second WebSocket broadcast cycles are reasonable.
- Continuous camera scanning (when added) will drain batteries fast.
- **Verdict:** Need battery-efficient scanning mode with motion detection to activate camera only when a QR code is likely in frame.

### 4.5 SMS/USSD Fallback (MISSING)
- **Zero** SMS or USSD integration.
- In East/West Africa, 30-40% of event attendees may not have smartphones.
- No alternative check-in for feature-phone users.
- **Verdict:** Critical gap. Need "Text CHECKIN 4829 to 12345" flow.

### 4.6 Multi-Language (MISSING)
- Entire UI is English-only.
- No i18n framework detected (no next-intl, no react-i18next).
- For Pan-African events: French (West/Central Africa), Swahili (East Africa), Amharic (Ethiopia), Arabic (North Africa) are essential.
- **Verdict:** i18n infrastructure needed before entering Francophone/Swahili markets.

### 4.7 Mobile Money Integration (PARTIAL)
- Payment system supports Stripe/Paystack (good for Africa).
- Ticket generation works after payment confirmation.
- But no explicit M-Pesa, MTN MoMo, or Flutterwave integration in check-in flow.
- **Verdict:** Payment-to-ticket flow works; mobile money just needs payment provider integration.

### 4.8 Data Costs (PASS)
- Ticket page uses offline caching — good for pay-per-MB users.
- PWA with service worker caching is already set up.
- QR code generation is client-side (no additional network request).
- **Verdict:** Good baseline, but scanner page (when built) must be <100KB.

---

## 5. RECOMMENDED ARCHITECTURE

### 5.1 Target Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    ATTENDEE DEVICE                         │
│                                                            │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ JWT-Signed   │  │ Rotating     │  │ SMS/USSD        │ │
│  │ QR Code      │  │ TOTP Token   │  │ Fallback PIN    │ │
│  └──────┬──────┘  └──────┬───────┘  └───────┬─────────┘ │
└─────────┼────────────────┼──────────────────┼────────────┘
          │                │                  │
          ▼                ▼                  ▼
┌──────────────────────────────────────────────────────────┐
│                    SCANNER DEVICE (PWA)                    │
│                                                            │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ Camera QR    │  │ Manual Code  │  │ NFC Tap         │ │
│  │ Scanner      │  │ Entry        │  │ (Premium)       │ │
│  └──────┬──────┘  └──────┬───────┘  └───────┬─────────┘ │
│         │                │                   │            │
│         ▼                ▼                   ▼            │
│  ┌─────────────────────────────────────────────────┐     │
│  │         OFFLINE VERIFICATION ENGINE              │     │
│  │  • Pre-cached attendee list + public key         │     │
│  │  • Local JWT signature verification              │     │
│  │  • Local check-in queue (IndexedDB)              │     │
│  │  • Sync when connectivity returns                │     │
│  └──────────────────────┬──────────────────────────┘     │
└─────────────────────────┼────────────────────────────────┘
                          │ (when online)
                          ▼
┌──────────────────────────────────────────────────────────┐
│              BACKEND SERVICES                              │
│                                                            │
│  ┌────────────────┐  ┌─────────────┐  ┌───────────────┐ │
│  │ Event Lifecycle │  │ Real-Time   │  │ SMS Gateway   │ │
│  │ Service         │  │ Service     │  │ (Africa's     │ │
│  │ (Check-in API)  │  │ (Dashboard) │  │  Talking)     │ │
│  └────────────────┘  └─────────────┘  └───────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### 5.2 Prioritized Roadmap

---

### P0: MUST-HAVE FOR LAUNCH (Week 1-2)

#### P0-1. Fix QR Code Security — JWT-Signed Tokens
Replace the current `SHA256(plaintext)[:8]` with proper JWT signing:
```
QR Code contains: JWT { sub: user_id, tid: ticket_id, eid: event_id, tcode: ticket_code, iat: issued_at, exp: event_end + 24h }
Signed with: RS256 using per-event keypair (public key shared with scanner, private key on server)
```
This enables OFFLINE verification — the scanner only needs the event's public key.

#### P0-2. Add Authorization to Check-In Mutation
Verify the authenticated user is an organizer/staff for the event before allowing check-in. Check organization membership + event ownership.

#### P0-3. Fix Race Condition with SELECT FOR UPDATE
Add `with_for_update()` to the ticket query in `check_in()`, matching the pattern already used in `crud_session_rsvp.py`.

#### P0-4. Add Camera-Based QR Scanner
Integrate `html5-qrcode` library into the organizer check-in tool. Must:
- Work on rear and front cameras
- Handle low-quality cameras (Tecno/Infinix budget phones)
- Provide instant visual + audio + haptic feedback
- Support torch/flashlight toggle for dark venues
- Fall back to manual entry

#### P0-5. Add Rate Limiting to GraphQL Check-In
Add rate limiting decorator: 60 check-ins/minute per user, 300/minute per IP.

#### P0-6. Enlarge QR Code on Attendee Ticket
Increase from 80px to 200px default, with tap-to-fullscreen for easy scanning.

---

### P1: MONTH 1 — Critical Competitive Features

#### P1-1. Offline-First PWA Scanner
Build a dedicated scanner page (`/scanner/[eventId]`) that:
1. On open: fetches event's public key + full attendee list (encrypted)
2. Caches both in IndexedDB via service worker
3. Scans QR codes and verifies JWT signatures entirely offline
4. Queues check-ins locally with timestamps
5. Syncs queue to server when connectivity returns (with conflict resolution)
6. Shows scan history even offline
7. Battery-efficient: uses motion detection to activate camera only when needed

#### P1-2. SMS/USSD Check-In Fallback
For attendees without smartphones:
1. On ticket purchase, generate a 4-6 digit PIN alongside the QR code
2. At event: attendee texts `CHECKIN <PIN>` to a shortcode
3. System validates PIN, checks in the ticket, sends confirmation SMS
4. Use Africa's Talking API (supports MTN, Airtel, Safaricom across 30+ countries)
5. Cost: ~$0.01/SMS — negligible even at scale

#### P1-3. Anti-Fraud: Photo Verification
1. During registration, capture attendee's selfie (optional, for premium events)
2. On check-in scan, show the registrant's photo next to the scan result
3. Staff visually confirms the person matches
4. No AI/facial recognition needed — just photo display for human verification

#### P1-4. Rotating QR Tokens (TOTP-like)
Replace static QR codes with rotating tokens:
1. Attendee app generates a new QR code every 30 seconds
2. QR contains: `JWT { ...ticket_data, nonce: TOTP(shared_secret, timestamp) }`
3. Scanner verifies TOTP is valid for current or previous time window
4. Screenshots become useless after 30 seconds
5. Requires app to be open — prevents casual sharing

#### P1-5. Real-Time Organizer Dashboard
Enhance the existing dashboard with:
- Live check-in counter with progress bar (checked_in / total)
- Check-in rate graph (check-ins per minute over time)
- Capacity alerts at 80%, 90%, 100%
- Per-gate/entrance breakdown
- No-show detection (registered but not checked in 30 min after event start)
- Exportable attendance report

#### P1-6. Session-Level Check-In for Paid Tickets
Currently session tracking only works via RSVP (free events). For paid conferences:
1. Add session check-in endpoints
2. Track which sessions each ticket holder actually attended
3. Show session-level attendance in organizer dashboard
4. Useful for CPD/CE credit tracking

---

### P2: QUARTER 1 — Best-in-Class Differentiators

#### P2-1. NFC Wristband Support
For premium events (festivals, multi-day conferences):
1. Pre-program NFC wristbands with ticket JWT
2. Staff taps wristband on NFC-enabled phone
3. Web NFC API reads tag → verifies JWT → checks in
4. No app needed for attendee — just wear the wristband

#### P2-2. Kiosk/Self-Service Mode
Turn any tablet into a self-check-in station:
1. Full-screen kiosk mode (`/kiosk/[eventId]`)
2. Attendee scans their own QR code or types email
3. Confirmation screen with name + event details
4. Auto-reset after 10 seconds for next attendee
5. Reduces staff needed by 50%+

#### P2-3. Geo-Fence Auto Check-In
For large outdoor events:
1. Attendee opts in to location-based check-in
2. When phone enters venue GPS boundary, trigger auto check-in
3. Background geofencing via service worker + Geolocation API
4. Confirmation push notification
5. Great for festivals, outdoor conferences

#### P2-4. Bluetooth Beacon Session Tracking
For multi-session conferences:
1. Place BLE beacons in each session room
2. Attendee app detects which room they're in
3. Auto-log session attendance (enter/exit times)
4. Generate per-attendee session history
5. Enable CPD/CE credit automation

#### P2-5. Multi-Language Support (i18n)
1. Integrate next-intl for frontend
2. Support: English, French, Swahili, Amharic, Arabic, Portuguese
3. Auto-detect from browser locale
4. Language picker in header
5. All check-in UI, error messages, and notifications translated

#### P2-6. Facial Recognition (VIP Events)
For high-security or VIP events:
1. Optional selfie capture during registration
2. On-device face matching at entry (TensorFlow.js or MediaPipe)
3. No cloud API calls — privacy-preserving
4. Staff sees match confidence score
5. Fallback to QR/manual for failed matches

#### P2-7. Badge Printing Integration
After successful check-in:
1. Auto-trigger badge print on networked printer
2. Badge template with: name, company, ticket type, QR code for sessions
3. Support Dymo, Brother, and Zebra label printers
4. Reduce check-in + badge time to <5 seconds total

---

## 6. IMPLEMENTATION PROMPTS

### P0-1: JWT-Signed QR Codes

```
TASK: Replace the current insecure QR code generation with cryptographically signed JWT tokens.

CURRENT STATE:
- File: event-lifecycle-service/app/models/ticket.py, method _generate_qr_data()
- Currently generates: "{ticket_id}|{ticket_code}|{event_id}|{sha256_hash[:8]}"
- The hash is just a checksum of the plaintext — NOT a signature. Anyone can forge it.

REQUIRED CHANGES:

1. Add a new file: event-lifecycle-service/app/services/ticket_management/qr_signing.py
   - Generate an RSA or Ed25519 keypair per event (or use a global signing key from env)
   - Store private key securely (env var or secrets manager)
   - Function: sign_ticket_qr(ticket_id, ticket_code, event_id, user_id) -> str
     - Creates JWT with claims: { sub: user_id, tid: ticket_id, eid: event_id, tcode: ticket_code, iat: now, exp: event_end + 24h }
     - Signs with RS256 or Ed25519
     - Returns base64url-encoded JWT string
   - Function: verify_ticket_qr(jwt_string, public_key) -> dict | None
     - Verifies signature and expiration
     - Returns decoded claims or None if invalid
   - Function: get_event_public_key(event_id) -> str
     - Returns the public key for offline verification

2. Modify event-lifecycle-service/app/models/ticket.py:
   - Update _generate_qr_data() to call sign_ticket_qr()
   - Add expires_at field to Ticket model (default: event end date + 24h)

3. Modify event-lifecycle-service/app/crud/ticket_crud.py:
   - In check_in(), add JWT verification as first step
   - Accept both legacy format (for migration) and JWT format

4. Add new endpoint: GET /api/v1/events/{event_id}/check-in/public-key
   - Returns the event's public key for offline scanner caching
   - No auth required (public keys are meant to be public)

5. Add Alembic migration for expires_at column on tickets table.

6. Update globalconnect/src/app/(attendee)/attendee/tickets/page.tsx:
   - Query should fetch qr_code_data (the JWT) instead of just ticketCode
   - Pass JWT string as QRCodeSVG value

DEPENDENCIES: PyJWT library (pip install PyJWT[crypto])
TESTS: Write tests for sign/verify roundtrip, expired token rejection, tampered token rejection
```

### P0-2: Authorization on Check-In Mutation

```
TASK: Add proper authorization to the checkInTicket GraphQL mutation.

CURRENT STATE:
- File: event-lifecycle-service/app/graphql/ticket_mutations.py, line 267-288
- Currently: Any authenticated user (with valid JWT) can check in any ticket for any event
- No organization membership or event ownership check

REQUIRED CHANGES:

1. In ticket_mutations.py, checkInTicket method:
   - Extract org_id from user JWT claims (user.get("orgId") or similar)
   - Query the event to get its organization_id
   - Verify user's org_id matches event's organization_id
   - OR: Check if user has 'event:validate_tickets' permission for this event
   - Raise PermissionError("You don't have permission to check in tickets for this event") if unauthorized

2. The authorization pattern should match what real-time-service already does:
   - validation.gateway.ts checks hasPermission(user, 'event:validate_tickets')
   - Apply the same check in the GraphQL layer

3. Consider creating a reusable decorator/dependency:
   - @require_event_permission('event:validate_tickets')
   - That extracts event_id from input, validates user has permission

4. Also fix reverseCheckIn mutation (line 290-303) — same authorization gap.

5. Also fix cancelTicket, transferTicket mutations — should require organizer role.

TESTS: Test that attendees cannot call checkInTicket. Test that organizers CAN check in their own events but not others'.
```

### P0-3: Fix Race Condition with SELECT FOR UPDATE

```
TASK: Fix the race condition in ticket check-in by adding database-level locking.

CURRENT STATE:
- File: event-lifecycle-service/app/crud/ticket_crud.py, method check_in() at line 169
- Current pattern: get(ticket_id) [no lock] → check can_check_in → update status
- Two concurrent requests can both see status='valid' and both proceed

REFERENCE: crud_session_rsvp.py already does this correctly with:
  db.query(SessionCapacity).filter(...).with_for_update().first()

REQUIRED CHANGES:

1. In ticket_crud.py, modify check_in():
   ```python
   def check_in(self, db, ticket_id, checked_in_by, location=None):
       # Use SELECT FOR UPDATE to prevent concurrent check-ins
       ticket = db.query(Ticket).filter(
           Ticket.id == ticket_id
       ).with_for_update().first()

       if not ticket:
           return None
       if not ticket.can_check_in:
           raise ValueError(f"Ticket cannot be checked in. Current status: {ticket.status}")

       ticket.status = "checked_in"
       ticket.checked_in_at = datetime.now(timezone.utc)
       ticket.checked_in_by = checked_in_by
       ticket.check_in_location = location
       ticket.updated_at = datetime.now(timezone.utc)

       db.commit()
       db.refresh(ticket)
       return ticket
   ```

2. Alternative approach (atomic UPDATE with WHERE):
   ```python
   result = db.query(Ticket).filter(
       Ticket.id == ticket_id,
       Ticket.status == 'valid'
   ).update({
       'status': 'checked_in',
       'checked_in_at': datetime.now(timezone.utc),
       'checked_in_by': checked_in_by,
       'check_in_location': location,
       'updated_at': datetime.now(timezone.utc)
   })
   if result == 0:
       raise ValueError("Ticket not found or already checked in")
   db.commit()
   ```

3. Apply same fix to reverse_check_in() method.

TESTS: Write a concurrent check-in test that spawns two threads checking in the same ticket — only one should succeed.
```

### P0-4: Camera-Based QR Scanner

```
TASK: Add camera-based QR code scanning to the organizer check-in tool.

CURRENT STATE:
- File: globalconnect/src/app/(platform)/dashboard/events/[eventId]/_components/ticket-check-in.tsx
- Currently only supports manual ticket code entry
- Uses Zod validation for XXX-XXX-XX format

REQUIRED CHANGES:

1. Install dependency: npm install html5-qrcode

2. Create new component: globalconnect/src/components/features/check-in/QrScanner.tsx
   - Use Html5Qrcode from html5-qrcode library
   - Props: { onScan: (code: string) => void, onError?: (error: string) => void, isActive: boolean }
   - Features:
     a. Camera selection (front/rear) with rear as default
     b. Torch/flashlight toggle for dark venues
     c. Configurable scan region (center box overlay)
     d. fps: 10 (balance between speed and battery)
     e. qrbox: { width: 250, height: 250 }
     f. aspectRatio: 1.0
     g. formatsToSupport: [Html5QrcodeSupportedFormats.QR_CODE]
   - Handle camera permissions gracefully
   - Show "Camera not available" fallback
   - Clean up camera on unmount

3. Modify ticket-check-in.tsx:
   - Add toggle between "Scan" and "Manual" modes
   - Default to "Scan" mode
   - When QR is scanned, auto-submit the ticket code
   - Add audio feedback: success beep + failure buzz (use Web Audio API)
   - Add haptic feedback: navigator.vibrate([200]) on success, [100, 50, 100] on failure
   - Show scan result overlay for 2 seconds (green checkmark or red X)
   - After successful scan, auto-ready for next scan

4. Add visual feedback:
   - Green flash overlay on successful check-in
   - Red flash overlay on failed check-in
   - Attendee name displayed prominently on success
   - Error reason displayed on failure

5. Optimize for low-end devices:
   - Reduce scan resolution if FPS drops below 5
   - Use requestAnimationFrame for smooth UI
   - Lazy-load the scanner component

TESTS: Manual testing on Chrome Android (Tecno Spark, Samsung A series). Verify camera works in low light.
```

### P0-5: Rate Limiting on GraphQL Check-In

```
TASK: Add rate limiting to the GraphQL check-in mutation.

CURRENT STATE:
- No rate limiting on checkInTicket GraphQL mutation
- Session RSVP mutations have rate limiting (5/min) — use as reference

REQUIRED CHANGES:

1. Check how RSVP rate limiting is implemented (rsvp_mutations.py) and apply same pattern.

2. Add to checkInTicket mutation: 60 check-ins/minute per user
   - This allows ~1 check-in/second which is fast enough for scanning
   - Prevents brute-force ticket code guessing

3. Add to reverseCheckIn: 10 reversals/minute per user

4. Return 429 Too Many Requests with Retry-After header when limit exceeded.

5. If using Redis-based rate limiting, use the pattern:
   Key: `ratelimit:checkin:{user_id}`
   TTL: 60 seconds
   Increment on each request, reject if > 60
```

### P1-1: Offline-First PWA Scanner

```
TASK: Build an offline-first PWA scanner page for event check-in.

CONTEXT: African events often lose internet connectivity when thousands of attendees connect to nearby cell towers. The scanner MUST work entirely offline.

ARCHITECTURE:
1. Route: /scanner/[eventId] (new page in globalconnect)
2. On page load (while online):
   a. Fetch event's JWT public key: GET /api/v1/events/{eventId}/check-in/public-key
   b. Fetch full attendee manifest: GET /api/v1/events/{eventId}/check-in/manifest
      - Returns: [{ ticketCode, attendeeName, ticketType, status }] (encrypted at rest)
   c. Cache both in IndexedDB via offline-storage.ts
   d. Register service worker for this page

3. Scanner page UI:
   - Camera viewfinder (full-width, top half)
   - Manual entry input (bottom, collapsible)
   - Connection status indicator (green/yellow/red)
   - Pending sync count badge
   - Recent scans list (last 20)
   - Stats bar: checked_in / total

4. Offline verification flow:
   a. Scan QR → extract JWT
   b. Verify JWT signature using cached public key (jose library)
   c. Check ticket code against cached manifest
   d. Check if already checked in (local state)
   e. If valid: mark as checked_in locally, add to sync queue
   f. If invalid: show error with reason

5. Sync mechanism:
   a. When connectivity returns, send queued check-ins to server
   b. POST /api/v1/events/{eventId}/check-in/bulk
   c. Handle conflicts (ticket already checked in by another scanner)
   d. Show sync status: "5 pending | 3 synced | 1 conflict"

6. Conflict resolution:
   - If server says "already checked in": accept server's timestamp, mark as synced
   - If server says "ticket not found": flag for manual review
   - Show conflict details to organizer

7. Service worker:
   - Pre-cache scanner page shell + dependencies
   - Cache event data on first fetch
   - Queue POST requests when offline (Workbox background sync)

DEPENDENCIES: html5-qrcode, jose (for JWT verification), workbox-webpack-plugin
TARGET: Must work on Tecno Spark 10 (Android 13, 3GB RAM, 8MP camera)
PAGE SIZE: <100KB initial load (critical for African data costs)
```

### P1-2: SMS/USSD Check-In Fallback

```
TASK: Implement SMS-based check-in for attendees without smartphones.

CONTEXT: In Africa, 30-40% of event attendees may use feature phones. They can't display QR codes. SMS works on every phone.

ARCHITECTURE:

1. On ticket generation (event-lifecycle-service):
   - Generate a 6-digit numeric PIN alongside the ticket code
   - Store in tickets table: check_in_pin column (new)
   - Send PIN via SMS: "Your check-in PIN for [Event] is: 482916. Text CHECKIN 482916 to +254xxxxxxx"

2. SMS Gateway Integration:
   - Use Africa's Talking API (covers 30+ African countries)
   - New service: event-lifecycle-service/app/services/sms/sms_gateway.py
   - Webhook endpoint: POST /api/v1/webhooks/sms/incoming
   - Parse incoming SMS: extract "CHECKIN <PIN>" pattern
   - Validate PIN against tickets table
   - Send confirmation SMS: "✓ Checked in! Welcome to [Event]. Gate: Main Entrance"
   - Or error SMS: "✗ Invalid PIN. Please check and try again."

3. Database changes:
   - Add check_in_pin (String(6), indexed) to tickets table
   - Add sms_check_in_number (String) to events table
   - Add Alembic migration

4. PIN security:
   - 6 digits = 1M combinations (sufficient for events up to 100K attendees)
   - PINs unique per event (not globally)
   - Rate limit: 3 SMS attempts per phone number per 10 minutes
   - PIN expires when event ends

5. Cost estimation:
   - Africa's Talking SMS: ~$0.01-0.03 per SMS
   - For 5,000 attendee event: ~$50-150 total SMS cost
   - Organizer pays (included in platform fee)

DEPENDENCIES: africas-talking Python SDK
COUNTRIES: Kenya, Nigeria, South Africa, Ghana, Tanzania, Rwanda, Uganda, Senegal
```

---

## APPENDIX: FILE INDEX

### event-lifecycle-service/app/models/
- `ticket.py` — Ticket model (QR, check-in status, transfer)
- `ticket_type.py` — Ticket types (pricing, capacity, sales windows)
- `registration.py` — Free event registrations
- `session_rsvp.py` — Session RSVPs
- `session_capacity.py` — Session capacity tracking
- `virtual_attendance.py` — Virtual session tracking
- `order.py` — Purchase orders
- `order_item.py` — Order line items
- `event.py` — Events (max_attendees field)
- `session.py` — Sessions (max_participants field)

### event-lifecycle-service/app/crud/
- `ticket_crud.py` — Ticket CRUD + check-in
- `crud_registration.py` — Registration CRUD
- `crud_session_rsvp.py` — RSVP CRUD with atomic capacity
- `crud_session_capacity.py` — Capacity operations
- `crud_virtual_attendance.py` — Virtual attendance
- `ticket_type_v2.py` — Ticket type CRUD
- `promo_code_crud.py` — Promo code CRUD

### event-lifecycle-service/app/services/ticket_management/
- `ticket_service.py` — Business logic orchestration

### event-lifecycle-service/app/graphql/
- `ticket_mutations.py` — Check-in + ticket mutations
- `ticket_queries.py` — Ticket queries + stats
- `rsvp_mutations.py` — RSVP mutations

### event-lifecycle-service/app/schemas/
- `ticket_management.py` — Pydantic schemas
- `registration.py` — Registration schemas

### globalconnect/src/
- `app/(platform)/dashboard/events/[eventId]/_components/ticket-check-in.tsx` — Organizer scanner
- `app/(platform)/dashboard/events/[eventId]/_components/ticket-management.tsx` — Ticket admin
- `app/(attendee)/attendee/tickets/page.tsx` — Attendee tickets
- `components/features/sessions/SessionRsvpButton.tsx` — Session RSVP
- `hooks/use-ticket-validation.ts` — Validation hook
- `hooks/use-ticket-metrics.ts` — Metrics hook
- `hooks/use-offline-query.ts` — Offline query wrapper
- `lib/offline-storage.ts` — IndexedDB storage
- `graphql/payments.graphql.ts` — Payment + check-in queries
- `graphql/attendee.graphql.ts` — Attendee queries

### real-time-service/src/
- `live/validation/validation.gateway.ts` — WebSocket validation
- `live/validation/validation.service.ts` — Validation logic
- `live/validation/dto/validate-ticket.dto.ts` — Validation DTO
- `live/dashboard/dashboard.service.ts` — Live dashboard
- `live/dashboard/dashboard.controller.ts` — Dashboard controller
- `app.gateway.ts` — Main WebSocket gateway
- `tickets/tickets.gateway.ts` — Ticket metrics
- `common/guards/ws-throttler.guard.ts` — WS rate limiting
- `common/guards/jwt-auth.guard.ts` — JWT auth
- `common/guards/internal-api-key.guard.ts` — Internal API key
- `shared/services/idempotency.service.ts` — Idempotency
- `common/utils/auth.utils.ts` — Auth utilities

---

*End of audit report. This system has a solid model/schema foundation but requires significant security hardening, offline capability, and UX improvements before production use at African events.*
