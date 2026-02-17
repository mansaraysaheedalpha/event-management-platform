# Venue Sourcing — Waitlist & Queue System API Contract

**The single source of truth for frontend and backend.**
Both sides build to this contract independently. If you need to change it, both sides must agree.

**Depends on:** Golden Directory API Contract + RFP System API Contract — venues, RFPs, and venue responses must exist

---

## Conventions (Same as RFP System + New Prefixes)

| Convention | Rule |
|---|---|
| ID format | Prefixed: `vwl_` (venue waitlist entries), `vas_` (venue availability signals) + 12-char hex |
| REST routes | Org-scoped: `/api/v1/organizations/{orgId}/waitlists/...`, Venue-scoped: `/api/v1/venues/{venueId}/availability/...` |
| Auth (REST) | `Authorization: Bearer <jwt>` — user object has `org_id`, `sub` (userId), `user_type` |
| Auth (GraphQL) | `info.context.user["orgId"]`, `info.context.user["sub"]` |
| Field casing | snake_case (Python/REST) ↔ camelCase (GraphQL/Frontend) |
| Updates | PATCH with optional fields, only non-null values applied |
| Rate limiting | Max 5 active waitlist entries per organizer (active = `waiting` or `offered`) |

---

## 1. Data Models

### 1.1 VenueWaitlistEntry

```
VenueWaitlistEntry {
  id:                     string       // "vwl_" + 12hex
  organization_id:        string       // FK to org (the organizer who joined the waitlist)
  venue_id:               string       // FK to Venue (the venue being waitlisted for)
  source_rfp_id:          string       // FK to RFP (the RFP that triggered this waitlist join)
  source_rfp_venue_id:    string       // FK to RFPVenue (specific venue response that was "unavailable")

  // Inherited context from source RFP (denormalized snapshot)
  desired_dates_start:    date?        // from RFP preferred_dates_start
  desired_dates_end:      date?        // from RFP preferred_dates_end
  dates_flexible:         boolean      // from RFP dates_flexible
  attendance_min:         int          // from RFP attendance_min
  attendance_max:         int          // from RFP attendance_max
  event_type:             string       // from RFP event_type
  space_requirements:     json         // from RFP space_requirements (array of layout types)

  // State
  status:                 WaitlistStatus  // enum
  queue_position:         int          // dynamically calculated, not stored

  // Hold tracking
  hold_offered_at:        datetime?    // when hold was offered
  hold_expires_at:        datetime?    // 48 hours after hold_offered_at
  hold_reminder_sent:     boolean      // whether 24h reminder was sent

  // Conversion
  converted_rfp_id:       string?      // FK to new RFP created on conversion

  // Cancellation
  cancellation_reason:    string?      // "no_longer_needed" | "found_alternative" | "declined_offer" | "other"
  cancellation_notes:     text?        // free text if reason = "other"

  // Expiry tracking
  expires_at:             datetime     // auto-calculated: 30 days after desired_dates_end, or 90 days after created_at
  still_interested_sent_at: datetime?  // when "still interested?" nudge was sent
  still_interested_responded: boolean  // whether they responded to the nudge

  // Circuit breaker tracking (computed per venue, NOT stored per-entry)
  // consecutive_no_responses is calculated dynamically via CRUD function get_consecutive_no_responses(venue_id)
  // No field needed on the model — it is derived from counting consecutive expired entries at queue front

  created_at:             datetime
  updated_at:             datetime
}
```

**WaitlistStatus enum:** `waiting`, `offered`, `converted`, `expired`, `cancelled`

**Cancellation reasons:** `no_longer_needed`, `found_alternative`, `declined_offer`, `nudge_declined`, `other`

### 1.2 VenueAvailabilitySignal

```
VenueAvailabilitySignal {
  id:                     string       // "vas_" + 12hex
  venue_id:               string       // FK to Venue
  signal_type:            SignalType   // enum
  source_rfp_id:          string?      // FK to RFP (null for manual signals)
  source_rfp_venue_id:    string?      // FK to RFPVenue
  signal_date:            date?        // the date this signal applies to (from RFP preferred dates)
  recorded_at:            datetime     // when the signal was recorded
  metadata:               json?        // additional context (attendance size, event type, etc.)
}
```

**SignalType enum:** `confirmed`, `tentative`, `unavailable`, `no_response`, `awarded`, `lost_to_competitor`, `rfp_cancelled`, `manual_available`, `manual_unavailable`

> **Note:** This table is **append-only**. Signals are never updated or deleted. The inference engine reads from it; RFP lifecycle events write to it.

### 1.3 Venue Model Changes (Additions to Existing Venue)

```
Venue (additions) {
  // Availability status (Tier 1)
  availability_status:           string    // "accepting_events" | "limited_availability" | "fully_booked" | "seasonal" | "not_set"
                                           // server_default: "not_set"

  // Inference tracking
  availability_last_inferred_at: datetime? // when the inference engine last ran for this venue
  availability_inferred_status:  string?   // what the inference engine computed (may differ from displayed status if manual override active)

  // Manual override
  availability_manual_override_at: datetime? // when venue owner last manually set the status
                                             // if this > availability_last_inferred_at, manual wins
}
```

**AvailabilityStatus enum:** `accepting_events`, `limited_availability`, `fully_booked`, `seasonal`, `not_set`

---

## 2. REST API Endpoints

### 2.1 Organizer Waitlist Management (Auth Required — Org Member)

Auth: JWT `org_id` must match `orgId` path param.

#### `POST /api/v1/organizations/{orgId}/waitlists`
Join a venue waitlist. Triggered from the comparison dashboard when a venue responded as unavailable.

**Rate limit:** Max 5 active waitlist entries per organizer. Return 429 if exceeded.

**Validation:**
- The source RFPVenue must have `status: responded` and `response.availability: unavailable`
- Organizer must not already have an active waitlist entry for the same venue (409)
- Max 5 active entries per organizer (429)

**Request Body:**
```json
{
  "source_rfp_venue_id": "rfv_abc123def456"
}
```

That's it — all context is inherited from the RFP and venue response. No additional form needed.

**Response: 201**
```json
{
  "id": "vwl_abc123def456",
  "organization_id": "org_001",
  "venue_id": "ven_kicc001",
  "venue_name": "KICC Nairobi",
  "source_rfp_id": "rfp_abc123",
  "source_rfp_title": "Annual Tech Conference 2026 Venue",
  "desired_dates_start": "2026-06-15",
  "desired_dates_end": "2026-06-17",
  "dates_flexible": false,
  "attendance_min": 200,
  "attendance_max": 300,
  "event_type": "conference",
  "status": "waiting",
  "queue_position": 3,
  "expires_at": "2026-07-17T00:00:00Z",
  "created_at": "2026-02-17T10:00:00Z"
}
```

#### `GET /api/v1/organizations/{orgId}/waitlists`
List organizer's waitlist entries.

**Query Parameters:**
```
status:     string?    // filter by status: waiting, offered, converted, expired, cancelled
active:     boolean?   // if true, only return waiting + offered entries
page:       int?       // default: 1
page_size:  int?       // default: 10, max: 50
```

**Response: 200**
```json
{
  "waitlist_entries": [
    {
      "id": "vwl_abc123def456",
      "venue_id": "ven_kicc001",
      "venue_name": "KICC Nairobi",
      "venue_slug": "kenyatta-international-convention-centre",
      "venue_cover_photo_url": "https://s3.../cover.jpg",
      "venue_availability_status": "fully_booked",
      "source_rfp_id": "rfp_abc123",
      "source_rfp_title": "Annual Tech Conference 2026 Venue",
      "desired_dates_start": "2026-06-15",
      "desired_dates_end": "2026-06-17",
      "event_type": "conference",
      "attendance_range": "200-300",
      "status": "waiting",
      "queue_position": 3,
      "hold_offered_at": null,
      "hold_expires_at": null,
      "expires_at": "2026-07-17T00:00:00Z",
      "created_at": "2026-02-17T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total_count": 2,
    "total_pages": 1
  }
}
```

#### `GET /api/v1/organizations/{orgId}/waitlists/{waitlistId}`
Get waitlist entry detail.

**Response: 200**
```json
{
  "id": "vwl_abc123def456",
  "organization_id": "org_001",
  "venue_id": "ven_kicc001",
  "venue_name": "KICC Nairobi",
  "venue_slug": "kenyatta-international-convention-centre",
  "venue_cover_photo_url": "https://s3.../cover.jpg",
  "venue_city": "Nairobi",
  "venue_country": "KE",
  "venue_availability_status": "fully_booked",
  "source_rfp_id": "rfp_abc123",
  "source_rfp_title": "Annual Tech Conference 2026 Venue",
  "desired_dates_start": "2026-06-15",
  "desired_dates_end": "2026-06-17",
  "dates_flexible": false,
  "attendance_min": 200,
  "attendance_max": 300,
  "event_type": "conference",
  "status": "offered",
  "queue_position": 1,
  "hold_offered_at": "2026-03-01T10:00:00Z",
  "hold_expires_at": "2026-03-03T10:00:00Z",
  "hold_remaining_seconds": 85423,
  "expires_at": "2026-07-17T00:00:00Z",
  "converted_rfp_id": null,
  "created_at": "2026-02-17T10:00:00Z",
  "updated_at": "2026-03-01T10:00:00Z"
}
```

**Note:** `hold_remaining_seconds` is computed server-side when status = `offered`. Null otherwise. The frontend uses this to initialize a countdown timer.

#### `POST /api/v1/organizations/{orgId}/waitlists/{waitlistId}/convert`
Convert the hold into a new pre-filled RFP. Only allowed when status = `offered` and hold has not expired.

**Validation:**
- Entry must be in `offered` state
- `hold_expires_at` must be in the future
- Organizer must not exceed 5 active RFPs (429 — check RFP rate limit too)

**Request Body:** (none — the new RFP is auto-generated from the source RFP)

**Response: 201**
```json
{
  "waitlist_entry": {
    "id": "vwl_abc123def456",
    "status": "converted",
    "converted_rfp_id": "rfp_new789"
  },
  "new_rfp": {
    "id": "rfp_new789",
    "title": "Annual Tech Conference 2026 Venue",
    "status": "draft",
    "venue_count": 1,
    "message": "New RFP created from waitlist hold. Review and send when ready."
  }
}
```

**Side effects:**
- Waitlist entry transitions to `converted`
- New RFP created in `draft` state, pre-filled from source RFP
- New RFP has exactly 1 venue: the waitlisted venue
- Response deadline set to 7 days from now (organizer can adjust before sending)
- Kafka event: `waitlist.converted`

#### `POST /api/v1/organizations/{orgId}/waitlists/{waitlistId}/cancel`
Cancel a waitlist entry. Allowed from `waiting` or `offered` state.

**Request Body:**
```json
{
  "reason": "found_alternative",
  "notes": null
}
```

**Response: 200**
```json
{
  "id": "vwl_abc123def456",
  "status": "cancelled",
  "cancellation_reason": "found_alternative"
}
```

**Side effects:**
- If was in `offered` state → triggers cascade to next person in queue
- Kafka event: `waitlist.cancelled`

---

### 2.2 Venue Availability Management (Auth Required — Venue Owner)

Auth: JWT `org_id` must match the venue's `organization_id`.

#### `GET /api/v1/venues/{venueId}/availability`
Get venue's current availability status and inference data.

**Response: 200**
```json
{
  "venue_id": "ven_kicc001",
  "availability_status": "limited_availability",
  "is_manual_override": false,
  "last_inferred_at": "2026-02-16T06:00:00Z",
  "inferred_status": "limited_availability",
  "manual_override_at": null,
  "signal_summary": {
    "period_days": 90,
    "total_responses": 12,
    "confirmed_count": 4,
    "tentative_count": 3,
    "unavailable_count": 5,
    "unavailable_ratio": 0.42
  }
}
```

#### `PUT /api/v1/venues/{venueId}/availability`
Manually set venue availability status. This creates a manual override that takes precedence over inference.

**Request Body:**
```json
{
  "availability_status": "accepting_events"
}
```

**Validation:** Status must be one of: `accepting_events`, `limited_availability`, `fully_booked`, `seasonal`

**Response: 200**
```json
{
  "venue_id": "ven_kicc001",
  "availability_status": "accepting_events",
  "is_manual_override": true,
  "manual_override_at": "2026-02-16T14:00:00Z"
}
```

**Side effects:**
- Sets `availability_manual_override_at` to now
- If new status is `accepting_events` and venue has waitlist entries → **triggers cascade**
- Kafka event: `venue.availability_changed`

#### `DELETE /api/v1/venues/{venueId}/availability/override`
Clear the manual override, returning to inference-driven status.

**Response: 200**
```json
{
  "venue_id": "ven_kicc001",
  "availability_status": "limited_availability",
  "is_manual_override": false,
  "reverted_to_inferred": true
}
```

---

### 2.3 Venue Availability (Public — No Auth)

#### `GET /api/v1/venues/{venueId}/availability/status`
Get the public-facing availability status badge. Used by the frontend for directory listings.

**Response: 200**
```json
{
  "venue_id": "ven_kicc001",
  "availability_status": "limited_availability",
  "badge_color": "yellow",
  "badge_label": "Limited Availability"
}
```

**Badge color mapping:**

| Status | Color | Label |
|---|---|---|
| `accepting_events` | `green` | Accepting Events |
| `limited_availability` | `yellow` | Limited Availability |
| `fully_booked` | `red` | Fully Booked |
| `seasonal` | `blue` | Seasonal Venue |
| `not_set` | `gray` | Status Unknown |

> **Performance note:** This endpoint is called for every venue card in the directory. It should be cached aggressively (Redis, 5-minute TTL). Alternatively, the availability status can be included directly in the existing venue list/detail endpoints to avoid N+1 calls.

---

### 2.4 Circuit Breaker Resolution (Auth Required — Venue Owner)

#### `POST /api/v1/venues/{venueId}/waitlist-circuit-breaker/resolve`
Venue owner confirms the waitlist should remain active after a circuit breaker pause. Resets the consecutive no-response counter and resumes the cascade.

**Auth:** Venue owner only (`venue.organization_id == jwt.org_id`).

**Request Body:**
```json
{
  "action": "resume"
}
```

**Validation:** `action` must be `resume`. The venue must have an active circuit breaker pause (3+ consecutive no-responses with no resolution).

**Response: 200**
```json
{
  "venue_id": "ven_kicc001",
  "circuit_breaker_resolved": true,
  "cascade_resumed": true,
  "next_entry_offered": "vwl_xyz789"
}
```

**Side effects:**
- Resets consecutive no-response counter for this venue to 0
- Triggers cascade to the next `waiting` entry in the FIFO queue
- Kafka event: `waitlist.circuit_breaker_resolved`

---

## 3. GraphQL Schema

### 3.1 Enums

```graphql
enum WaitlistStatus {
  WAITING
  OFFERED
  CONVERTED
  EXPIRED
  CANCELLED
}

enum CancellationReason {
  NO_LONGER_NEEDED
  FOUND_ALTERNATIVE
  DECLINED_OFFER
  NUDGE_DECLINED
  OTHER
}

enum AvailabilityStatus {
  ACCEPTING_EVENTS
  LIMITED_AVAILABILITY
  FULLY_BOOKED
  SEASONAL
  NOT_SET
}

enum SignalType {
  CONFIRMED
  TENTATIVE
  UNAVAILABLE
  NO_RESPONSE
  AWARDED
  LOST_TO_COMPETITOR
  RFP_CANCELLED
  MANUAL_AVAILABLE
  MANUAL_UNAVAILABLE
}
```

### 3.2 Types

```graphql
type VenueWaitlistEntryType {
  id: String!
  organizationId: String!
  venueId: String!
  venueName: String!
  venueSlug: String!
  venueCoverPhotoUrl: String
  venueCity: String
  venueCountry: String
  venueAvailabilityStatus: AvailabilityStatus!

  sourceRfpId: String!
  sourceRfpTitle: String!
  sourceRfpVenueId: String!

  desiredDatesStart: Date
  desiredDatesEnd: Date
  datesFlexible: Boolean!
  attendanceMin: Int!
  attendanceMax: Int!
  eventType: String!

  status: WaitlistStatus!
  queuePosition: Int                  # nullable — returns null for terminal states (converted, expired, cancelled)

  holdOfferedAt: DateTime
  holdExpiresAt: DateTime
  holdRemainingSeconds: Int               # computed, null if not in offered state
  holdReminderSent: Boolean!

  convertedRfpId: String

  cancellationReason: CancellationReason
  cancellationNotes: String

  expiresAt: DateTime!
  stillInterestedSentAt: DateTime
  stillInterestedResponded: Boolean!

  createdAt: DateTime!
  updatedAt: DateTime!
}

type WaitlistEntryListResult {
  entries: [VenueWaitlistEntryType!]!
  totalCount: Int!
  page: Int!
  pageSize: Int!
  totalPages: Int!
}

type WaitlistConversionResult {
  waitlistEntry: VenueWaitlistEntryType!
  newRfp: RFPType!                         # the pre-filled RFP created from conversion
}

type VenueAvailabilityType {
  venueId: String!
  availabilityStatus: AvailabilityStatus!
  isManualOverride: Boolean!
  lastInferredAt: DateTime
  inferredStatus: AvailabilityStatus
  manualOverrideAt: DateTime
  signalSummary: AvailabilitySignalSummary
}

type AvailabilitySignalSummary {
  periodDays: Int!
  totalResponses: Int!
  confirmedCount: Int!
  tentativeCount: Int!
  unavailableCount: Int!
  unavailableRatio: Float!
}

type AvailabilityBadge {
  venueId: String!
  availabilityStatus: AvailabilityStatus!
  badgeColor: String!
  badgeLabel: String!
}
```

### 3.3 Venue Type Extension

Add these fields to the existing `VenueType` and `VenueFullType` in the Golden Directory GraphQL schema:

```graphql
# Add to existing VenueType
extend type VenueType {
  availabilityStatus: AvailabilityStatus!
  availabilityBadgeColor: String!
  availabilityBadgeLabel: String!
}

# Add to existing VenueFullType
extend type VenueFullType {
  availabilityStatus: AvailabilityStatus!
  availabilityBadgeColor: String!
  availabilityBadgeLabel: String!
  availabilityIsManualOverride: Boolean     # only visible to venue owner
}
```

> **Implementation note:** These are resolved fields on the existing venue types, not a separate query. The resolver reads the `availability_status` column from the Venue model and computes badge color/label.

### 3.4 Queries

```graphql
type Query {
  # --- Organizer Waitlist (auth required) ---
  myWaitlistEntries(
    status: WaitlistStatus
    activeOnly: Boolean
    page: Int
    pageSize: Int
  ): WaitlistEntryListResult!

  waitlistEntry(id: String!): VenueWaitlistEntryType

  # --- Venue Owner Availability (auth required — venue owner) ---
  venueAvailability(venueId: String!): VenueAvailabilityType!

  # --- Public ---
  venueAvailabilityBadge(venueId: String!): AvailabilityBadge!
}
```

### 3.5 Mutations

```graphql
type Mutation {
  # --- Organizer Waitlist ---
  joinVenueWaitlist(
    sourceRfpVenueId: String!
  ): VenueWaitlistEntryType!

  convertWaitlistHold(
    waitlistId: String!
  ): WaitlistConversionResult!

  cancelWaitlistEntry(
    waitlistId: String!
    reason: CancellationReason!
    notes: String
  ): VenueWaitlistEntryType!

  respondStillInterested(
    waitlistId: String!
    interested: Boolean!
  ): VenueWaitlistEntryType!

  # --- Venue Owner Availability ---
  setVenueAvailability(
    venueId: String!
    status: AvailabilityStatus!
  ): VenueAvailabilityType!

  clearVenueAvailabilityOverride(
    venueId: String!
  ): VenueAvailabilityType!

  # --- Circuit Breaker ---
  resolveWaitlistCircuitBreaker(
    venueId: String!
  ): Boolean!
}
```

---

## 4. Notification Events

| Event Key | Recipient | Channels | Trigger |
|---|---|---|---|
| `waitlist.joined` | Organizer | In-app + Email | Organizer joins waitlist |
| `waitlist.hold_offered` | Organizer | In-app + Email + WhatsApp | Hold offered (their turn in queue) |
| `waitlist.hold_reminder` | Organizer | Email + WhatsApp | 24h before hold expires |
| `waitlist.hold_expired` | Organizer | In-app + Email | Hold expired without action |
| `waitlist.converted` | Organizer | In-app | Successfully converted to new RFP |
| `waitlist.position_changed` | Organizer | In-app | Queue position changed (someone ahead cancelled) |
| `waitlist.still_interested` | Organizer | Email | 60-day nudge for general entries |
| `waitlist.auto_expired` | Organizer | In-app + Email | Entry auto-expired (date passed or 90 days) |
| `waitlist.circuit_breaker` | Venue owner | In-app + Email | 3 consecutive no-responses, confirm to continue |
| `venue.availability_changed` | (Internal) | Kafka only | Venue availability status changed (triggers cascade check) |

---

## 5. Background Jobs (APScheduler)

| Task | Schedule | Description |
|---|---|---|
| `process_waitlist_hold_expiry` | Every 1 minute | Checks for expired holds (hold_expires_at < now). Transitions to `expired`, triggers cascade to next person. Tracks consecutive no-responses for circuit breaker. |
| `send_waitlist_hold_reminders` | Every 15 minutes | Sends 24h-before reminders to organizers with active holds who haven't been reminded yet. |
| `process_waitlist_auto_expiry` | Every 1 hour | Expires entries where: (a) desired dates passed + 30 days, or (b) 90 days since creation for flexible-date entries. |
| `send_still_interested_nudges` | Daily at 10:00 UTC | Sends "still interested?" emails to general entries at 60 days. |
| `process_nudge_expiry` | Daily at 10:00 UTC | Expires entries where `still_interested_sent_at + 7 days < now()` AND `still_interested_responded=False`. |
| `run_availability_inference` | Every 6 hours | Runs the signal-driven availability inference engine for all venues with recent signals. Updates inferred status. Triggers cascade if status improves. |
| `process_circuit_breaker_expiry` | Daily at 00:00 UTC | Deactivates waitlists where circuit breaker was triggered and venue owner didn't respond within 7 days. |

---

## 6. Kafka Events (for Analytics & Phase 2 AI)

Every waitlist state transition emits a Kafka event to the `waitlist-events` topic:

```json
{
  "event_type": "waitlist.hold_offered",
  "waitlist_entry_id": "vwl_abc123",
  "venue_id": "ven_kicc001",
  "organization_id": "org_001",
  "source_rfp_id": "rfp_abc123",
  "previous_status": "waiting",
  "new_status": "offered",
  "metadata": {
    "queue_position": 1,
    "queue_depth": 4,
    "hold_expires_at": "2026-03-03T10:00:00Z"
  },
  "timestamp": "2026-03-01T10:00:00Z"
}
```

**Event types:** `waitlist.joined`, `waitlist.hold_offered`, `waitlist.hold_expired`, `waitlist.converted`, `waitlist.cancelled`, `waitlist.auto_expired`, `waitlist.circuit_breaker_triggered`, `waitlist.circuit_breaker_resolved`, `venue.availability_inferred`, `venue.availability_manual_set`

---

## 7. Signal Recording (RFP Integration Points)

Signals are recorded automatically when RFP lifecycle events occur. **No new endpoints needed** — these are side effects within existing RFP code.

| RFP Event | Signal Recorded | Signal Type |
|---|---|---|
| Venue submits response: `confirmed` | Record signal | `confirmed` |
| Venue submits response: `tentative` | Record signal | `tentative` |
| Venue submits response: `unavailable` | Record signal | `unavailable` |
| RFP deadline passes, venue didn't respond | Record signal | `no_response` |
| Organizer awards venue | Record signal | `awarded` |
| Organizer awards different venue (this venue loses) | Record signal | `lost_to_competitor` |
| Organizer closes/cancels RFP | Record signal for all targeted venues | `rfp_cancelled` |
| Venue owner manually sets availability | Record signal | `manual_available` or `manual_unavailable` |

**Implementation:** Add signal recording calls to the existing RFP endpoint handlers and background jobs. Each signal records the `venue_id`, `signal_type`, `source_rfp_id`, `source_rfp_venue_id`, and `signal_date` (from RFP's preferred dates).

---

## 8. Waitlist Cascade Logic

When a venue becomes available (either through inference or manual override), the cascade engine runs:

```python
def trigger_cascade(venue_id: str):
    """Offer hold to the next eligible person in the FIFO queue."""

    # Check circuit breaker
    consecutive_no_responses = get_consecutive_no_responses(venue_id)
    if consecutive_no_responses >= 3:
        # Circuit breaker active — notify venue owner, don't cascade
        send_circuit_breaker_notification(venue_id)
        return

    # Find the next person in the queue
    next_entry = get_next_waiting_entry(venue_id)  # ORDER BY created_at ASC, status = 'waiting', LIMIT 1
    if next_entry is None:
        return  # Queue empty

    # Offer the hold
    next_entry.status = "offered"
    next_entry.hold_offered_at = now()
    next_entry.hold_expires_at = now() + timedelta(hours=48)

    # Send notifications
    send_hold_offered_notification(next_entry)

    # Emit Kafka event
    emit_kafka_event("waitlist.hold_offered", next_entry)
```

**Cascade is triggered by:**
1. Hold expiry (automatic — previous person's hold expired)
2. Cancellation (organizer cancelled or declined)
3. Availability improvement (inference engine or manual override)

**Cascade is NOT triggered by:**
- Conversion (the hold was used — no need to offer to next person)
- Auto-expiry of a `waiting` entry (they just aged out, no availability change)

---

## 9. Auth & Permissions Summary

| Endpoint Group | Auth Required | Who Can Access |
|---|---|---|
| Organizer waitlists (`/organizations/{orgId}/waitlists/*`) | Yes | Org members where `jwt.org_id == orgId` |
| Venue availability management (`/venues/{venueId}/availability`) | Yes | Org members who own the venue (`venue.organization_id == jwt.org_id`) |
| Venue availability status (public badge) (`/venues/{venueId}/availability/status`) | No | Everyone (cached, public data) |

---

## 10. Error Responses

All errors follow the existing format:
```json
{
  "detail": "Human-readable error message"
}
```

| Status | When |
|---|---|
| 400 | Invalid input (invalid cancellation reason, invalid availability status) |
| 401 | Missing or invalid JWT |
| 403 | JWT valid but user doesn't have permission (wrong org, venue not owned) |
| 404 | Waitlist entry or venue not found |
| 409 | Conflict (already on waitlist for this venue, hold already expired, entry not in correct state) |
| 422 | Invalid state transition (e.g., converting when not in `offered` state, cancelling a terminal entry) |
| 429 | Rate limited (max 5 active waitlist entries per organizer) |
