# Venue Sourcing RFP — Backend Implementation Tasks

**Service:** `event-lifecycle-service` (Python/FastAPI/SQLAlchemy)
**Reference:** [API_CONTRACT_RFP.md](API_CONTRACT_RFP.md) — build exactly to this contract
**Reference:** [../VENUE_SOURCING_RFP_SPEC.md](../VENUE_SOURCING_RFP_SPEC.md) — feature spec
**Depends on:** Golden Directory (Phase 1, Section 1) must be built first — venues, spaces, amenities models must exist

---

## Task R-B1: Database Models & Migration

**Files to create/modify:**

- `app/models/rfp.py` — NEW
- `app/models/rfp_venue.py` — NEW
- `app/models/venue_response.py` — NEW
- `app/models/negotiation_message.py` — NEW (schema only, no endpoints)
- `app/models/__init__.py` — register new models
- `alembic/versions/xxx_rfp_system.py` — NEW migration

**What to do:**

1. Create `RFP` model with all columns from API contract section 1.1:
   - `id` (primary key, `rfp_` + 12hex, same pattern as `venue.py`)
   - `organization_id` (FK concept — string, not enforced FK since orgs are in another service)
   - All RFP fields: `title`, `event_type`, `attendance_min`, `attendance_max`, `preferred_dates_start`, `preferred_dates_end`, `dates_flexible`, `duration`, `space_requirements` (JSON), `required_amenity_ids` (JSON array), `catering_needs`, `budget_min`, `budget_max`, `budget_currency`, `preferred_currency`, `additional_notes`, `response_deadline`, `linked_event_id` (nullable FK to events table)
   - Status fields: `status` (default `draft`), `sent_at`
   - Template fields: `is_template` (default false), `template_name` (nullable)
   - Timestamps: `created_at`, `updated_at`
   - Use `String` for enum columns (same pattern as venue status)
   - Store `space_requirements` and `required_amenity_ids` as JSON columns (PostgreSQL JSON type)

2. Create `RFPVenue` model (junction table):
   - `id` (`rfv_` + 12hex)
   - `rfp_id` (FK to RFP, indexed)
   - `venue_id` (FK to Venue, indexed)
   - `status` (default `received`)
   - Tracking: `notified_at`, `viewed_at`, `responded_at`
   - Pre-computed: `capacity_fit` (string), `amenity_match_pct` (float)
   - Unique constraint: `(rfp_id, venue_id)` — one junction per venue per RFP
   - Timestamps: `created_at`, `updated_at`

3. Create `VenueResponse` model:
   - `id` (`vrs_` + 12hex)
   - `rfp_venue_id` (FK to RFPVenue, unique — one response per junction)
   - All response fields from API contract section 1.3
   - `total_estimated_cost` (decimal, computed before insert)
   - Store `included_amenity_ids` as JSON, `extra_cost_amenities` as JSON, `alternative_dates` as JSON
   - Timestamps: `created_at`, `updated_at`

4. Create `NegotiationMessage` model (schema only):
   - `id` (`ngm_` + 12hex)
   - `rfp_venue_id` (FK to RFPVenue)
   - `sender_type`, `message_type`, `content` (JSON)
   - `created_at`

5. Add relationships:
   - `RFP.venues` → `RFPVenue` (one-to-many, cascade delete)
   - `RFPVenue.rfp` → `RFP` (many-to-one)
   - `RFPVenue.venue` → `Venue` (many-to-one, NO cascade — don't delete venues)
   - `RFPVenue.response` → `VenueResponse` (one-to-one, cascade delete)

6. Create Alembic migration. Ensure it runs on existing DB with venue data.

**Acceptance criteria:**
- [ ] All models created with correct types, constraints, indexes
- [ ] Unique constraint on `(rfp_id, venue_id)` in RFPVenue
- [ ] Unique constraint on `rfp_venue_id` in VenueResponse
- [ ] JSON columns work correctly for arrays
- [ ] Migration runs successfully
- [ ] NegotiationMessage table exists but has no endpoints

---

## Task R-B2: Pydantic Schemas

**Files to create:**

- `app/schemas/rfp.py` — NEW
- `app/schemas/rfp_venue.py` — NEW
- `app/schemas/venue_response.py` — NEW

**What to do:**

1. Create RFP schemas:
   - `RFPCreate` — all fields from API contract create endpoint
   - `RFPUpdate` — all fields optional
   - `RFPResponse` — full response shape with nested venues
   - `RFPListItem` — lightweight list item (no nested venues, includes `venue_count`, `response_count`)
   - `RFPListResult` — paginated result
   - Validate: `attendance_min` < `attendance_max`, `budget_min` < `budget_max`, `response_deadline` in future (on create), `event_type` is valid enum value, `space_requirements` values are valid layout types

2. Create RFPVenue schemas:
   - `RFPVenueResponse` — with denormalized venue info
   - `AddVenuesRequest` — `{ venue_ids: list[str] }`
   - `PreSendVenueFit` — fit indicator per venue
   - `PreSendSummary` — list of fits

3. Create VenueResponse schemas:
   - `VenueResponseCreate` — structured response form input
   - `VenueResponseResponse` — full response data
   - `ExtraCostAmenity` — `{ amenity_id, name, price }`
   - Validate: `currency` is valid ISO 4217, `availability` is valid enum, at least `proposed_space_id` or `proposed_space_name` provided if availability is `confirmed` or `tentative`

4. Create comparison schemas:
   - `ComparisonVenue` — venue + response + calculated fields
   - `ComparisonDashboard` — full comparison data with exchange rates and badges

**Acceptance criteria:**
- [ ] All request/response shapes match API contract exactly
- [ ] Validation rules enforced (attendance range, budget range, deadline, enums)
- [ ] `from_attributes = True` on all response schemas

---

## Task R-B3: CRUD Layer

**Files to create:**

- `app/crud/crud_rfp.py` — NEW
- `app/crud/crud_rfp_venue.py` — NEW
- `app/crud/crud_venue_response.py` — NEW

**What to do:**

1. RFP CRUD:
   - `create(db, org_id, data)` — create draft RFP, enforce 5 active RFP limit per org
   - `get(db, rfp_id)` — with joined venues
   - `list_by_org(db, org_id, status?, page, page_size)` — paginated
   - `update(db, rfp_id, data)` — only if status = `draft`
   - `delete(db, rfp_id)` — only if status = `draft`
   - `send(db, rfp_id)` — transition to `sent`, set `sent_at`, validate has venues + deadline in future
   - `extend_deadline(db, rfp_id, new_deadline)` — validate new > current
   - `close(db, rfp_id, reason?)` — transition to `closed`
   - `duplicate(db, rfp_id)` — clone to new draft
   - `transition_status(db, rfp_id, new_status)` — enforce state machine transitions
   - `count_active_rfps(db, org_id)` — count RFPs in non-terminal states

2. RFPVenue CRUD:
   - `add_venues(db, rfp_id, venue_ids)` — bulk add, compute fit indicators, enforce max 10
   - `remove_venue(db, rfp_id, venue_id)` — only if RFP is `draft`
   - `get_venues_for_rfp(db, rfp_id)` — with venue details
   - `mark_viewed(db, rfp_venue_id)` — transition `received` → `viewed`, set `viewed_at`
   - `shortlist(db, rfv_id)` — transition `responded` → `shortlisted`
   - `award(db, rfv_id)` — transition to `awarded`, also transition RFP to `awarded`
   - `decline(db, rfv_id, reason?)` — transition to `declined`
   - `mark_no_response(db, rfp_id)` — bulk mark all non-responded venues (for deadline job)
   - `compute_capacity_fit(venue_capacity, max_attendance)` — green/yellow/red logic from spec
   - `compute_amenity_match(venue_amenity_ids, required_amenity_ids)` — percentage calculation

3. VenueResponse CRUD:
   - `create(db, rfp_venue_id, data)` — create response, auto-calculate `total_estimated_cost`, denormalize space name/capacity from VenueSpace record
   - `get_by_rfp_venue(db, rfp_venue_id)` — get existing response
   - `get_comparison_data(db, rfp_id)` — all responses for comparison dashboard with calculated fields

4. Fit indicator calculations:
   - **Capacity fit:** green (100-150%), yellow (80-99% or 151-200%), red (<80% or >200%)
   - **Amenity match:** `len(intersection) / len(required) * 100`
   - **Price indicator:** compare venue's min full_day price against budget range

**Acceptance criteria:**
- [ ] State machine transitions enforced (invalid transitions raise 422)
- [ ] Rate limit: max 5 active RFPs per org enforced
- [ ] Max 10 venues per RFP enforced
- [ ] Fit indicators correctly computed
- [ ] Total estimated cost correctly summed (including catering * attendance_max)
- [ ] Space name/capacity denormalized from VenueSpace on response creation

---

## Task R-B4: REST API — Organizer RFP Endpoints

**Files to create:**

- `app/api/v1/endpoints/rfps.py` — NEW

**What to do:**

1. Implement all organizer endpoints from API contract sections 2.1-2.4:
   - `POST /organizations/{orgId}/rfps` — create draft
   - `GET /organizations/{orgId}/rfps` — list with status filter + pagination
   - `GET /organizations/{orgId}/rfps/{rfpId}` — detail with venues
   - `PATCH /organizations/{orgId}/rfps/{rfpId}` — update draft
   - `DELETE /organizations/{orgId}/rfps/{rfpId}` — delete draft
   - `POST /organizations/{orgId}/rfps/{rfpId}/venues` — add venues
   - `DELETE /organizations/{orgId}/rfps/{rfpId}/venues/{venueId}` — remove venue
   - `GET /organizations/{orgId}/rfps/{rfpId}/pre-send-summary` — fit indicators
   - `POST /organizations/{orgId}/rfps/{rfpId}/send` — send RFP
   - `POST /organizations/{orgId}/rfps/{rfpId}/extend-deadline` — extend
   - `POST /organizations/{orgId}/rfps/{rfpId}/close` — close
   - `POST /organizations/{orgId}/rfps/{rfpId}/duplicate` — clone

2. Auth: Same pattern as venue endpoints — `current_user.org_id != orgId` → 403

3. On `send`: trigger notification dispatch for all venue owners (see Task R-B7)

4. Register routes in `app/api/v1/api.py`

**Acceptance criteria:**
- [ ] All endpoints return shapes matching API contract
- [ ] Rate limit (5 active RFPs) enforced on create
- [ ] State transitions enforced (can't update a sent RFP, can't delete a sent RFP)
- [ ] Venue limit (10 per RFP) enforced on add
- [ ] 429 returned when rate limited

---

## Task R-B5: REST API — Venue Decision Endpoints

**Files to create/modify:**

- `app/api/v1/endpoints/rfps.py` — EXTEND (add decision routes)

**What to do:**

1. Implement venue decision endpoints from API contract section 2.4:
   - `POST /organizations/{orgId}/rfps/{rfpId}/venues/{rfvId}/shortlist`
   - `POST /organizations/{orgId}/rfps/{rfpId}/venues/{rfvId}/award`
   - `POST /organizations/{orgId}/rfps/{rfpId}/venues/{rfvId}/decline`

2. Implement comparison dashboard endpoint from API contract section 2.5:
   - `GET /organizations/{orgId}/rfps/{rfpId}/compare`
   - Must fetch exchange rates from Redis cache
   - Compute `total_in_preferred_currency` for each response
   - Compute badges: `best_value` (lowest total in preferred currency), `best_match` (highest amenity match %)

3. On `award`: trigger acceptance notification to venue owner, transition RFP status to `awarded`, decline all other venues with status `responded`/`shortlisted` automatically

4. On `decline`: trigger decline notification to venue owner

**Acceptance criteria:**
- [ ] State transitions enforced on all venue actions
- [ ] Only one venue can be awarded per RFP
- [ ] Awarding auto-declines all other responded/shortlisted venues
- [ ] Comparison dashboard correctly calculates currency conversions
- [ ] Badges correctly assigned

---

## Task R-B6: REST API — Venue Owner Endpoints

**Files to create:**

- `app/api/v1/endpoints/venue_rfps.py` — NEW

**What to do:**

1. Implement venue owner endpoints from API contract section 2.6:
   - `GET /venues/{venueId}/rfps` — RFP inbox with pagination
   - `GET /venues/{venueId}/rfps/{rfpId}` — RFP detail (side effect: mark as viewed)
   - `POST /venues/{venueId}/rfps/{rfpId}/respond` — submit structured response

2. Auth: Verify `venue.organization_id == current_user.org_id`

3. On view: transition venue status `received` → `viewed`, set `viewed_at`

4. On respond:
   - Validate deadline not passed
   - Validate no existing response
   - Auto-calculate `total_estimated_cost`:
     ```
     total = space_rental_price
           + (catering_price_per_head * rfp.attendance_max)
           + av_equipment_fees
           + setup_cleanup_fees
           + other_fees
           + sum(extra_cost_amenity.price for each)
     ```
   - Denormalize `proposed_space_name` and `proposed_space_capacity` from VenueSpace record
   - Transition venue status → `responded`, set `responded_at`
   - If first response: transition RFP `sent` → `collecting_responses`
   - If all venues responded: transition RFP → `review`
   - Trigger notification to organizer

5. Include venue's own spaces in the RFP detail response (so venue can select which space to propose)

6. Register routes in `app/api/v1/api.py`

**Acceptance criteria:**
- [ ] Auth correctly verifies venue ownership
- [ ] Viewed side-effect only triggers on first view
- [ ] Response validation: deadline check, no duplicates
- [ ] Total cost correctly calculated
- [ ] Space data correctly denormalized
- [ ] RFP status auto-transitions on first/last response
- [ ] Organizer notified on response

---

## Task R-B7: Notification Service

**Files to create:**

- `app/utils/rfp_notifications.py` — NEW

**What to do:**

1. Create a channel-agnostic notification dispatcher:
   ```python
   async def dispatch_rfp_notification(
       event_key: str,       # e.g., "rfp.new_request"
       recipient_type: str,  # "organizer" | "venue_owner"
       recipient_data: dict, # name, email, whatsapp, org_id
       payload: dict         # event-specific data
   )
   ```

2. Implement notification handlers for each event:
   - `rfp.new_request` → Email (Resend) + WhatsApp (Africa's Talking) + In-app
   - `rfp.deadline_reminder` → Email + WhatsApp
   - `rfp.venue_responded` → Email + In-app
   - `rfp.all_responded` → Email + In-app
   - `rfp.deadline_passed` → Email + In-app
   - `rfp.proposal_accepted` → Email + WhatsApp + In-app
   - `rfp.proposal_declined` → Email + In-app
   - `rfp.deadline_extended` → Email + WhatsApp

3. Email delivery: Use existing Resend integration (direct API call or Kafka publish to `payment.emails.v1` topic — follow existing pattern from `app/utils/waitlist_emails.py`)

4. WhatsApp delivery: Create `app/utils/whatsapp.py` with Africa's Talking WhatsApp API integration:
   - Template-based messages (templates defined in spec)
   - Include deep link to RFP in venue dashboard
   - Track delivery status if API supports it
   - Graceful fallback — if WhatsApp fails, log error but don't fail the operation

5. In-app notifications: Publish to Redis pub/sub channel for real-time-service to consume, OR create a notification record in the database. Follow existing notification pattern if one exists.

**Acceptance criteria:**
- [ ] All 8 notification events implemented
- [ ] Email sends successfully via Resend
- [ ] WhatsApp sends with templated messages
- [ ] In-app notification created/published
- [ ] Failures in one channel don't block other channels
- [ ] No notification sent to venues that have already responded (for reminders/deadline extended)

---

## Task R-B8: Celery Background Jobs

**Files to modify:**

- `app/tasks.py` — ADD new tasks

**What to do:**

1. Add `process_rfp_deadlines` task:
   ```python
   @celery_app.task
   def process_rfp_deadlines():
       """Runs every 5 minutes. Checks for RFPs past deadline."""
       # Find RFPs in 'sent' or 'collecting_responses' where deadline < now()
       # For 'sent' with 0 responses → transition to 'expired'
       # For 'collecting_responses' → transition to 'review'
       # Mark all non-responded venues as 'no_response'
       # Send 'rfp.deadline_passed' notification to organizer
   ```

2. Add `send_rfp_deadline_reminders` task:
   ```python
   @celery_app.task
   def send_rfp_deadline_reminders():
       """Runs every hour. Sends 24h-before reminders."""
       # Find RFPs where deadline is 23-25 hours from now
       # For each non-responded venue, send 'rfp.deadline_reminder'
       # Track which reminders have been sent (avoid duplicates)
   ```

3. Add `refresh_exchange_rates` task:
   ```python
   @celery_app.task
   def refresh_exchange_rates():
       """Runs daily. Fetches exchange rates and caches in Redis."""
       # Fetch from exchangerate-api.com (free tier)
       # Cache in Redis with key 'exchange_rates:{base_currency}'
       # TTL: 25 hours (overlap to prevent gaps)
       # Support multiple base currencies: USD, KES, NGN, SLE, ZAR, GHS
   ```

4. Register periodic tasks in Celery Beat schedule (in `app/worker.py` or celery config)

**Acceptance criteria:**
- [ ] Deadline processing correctly transitions states
- [ ] Reminders sent exactly once (no duplicates)
- [ ] Exchange rates cached with correct TTL
- [ ] Tasks handle DB errors gracefully (retry with backoff)
- [ ] Tasks don't process same RFP twice in concurrent runs (use DB-level locking or status flags)

---

## Task R-B9: Exchange Rate Service

**Files to create:**

- `app/utils/exchange_rates.py` — NEW

**What to do:**

1. Create exchange rate utility:
   ```python
   async def get_exchange_rates(base: str, targets: list[str] = None) -> dict:
       """Get rates from Redis cache, falling back to API if cache miss."""

   async def convert_amount(amount: float, from_currency: str, to_currency: str) -> float:
       """Convert using cached rates."""

   async def fetch_and_cache_rates(base: str):
       """Fetch from API and store in Redis."""
   ```

2. Use `exchangerate-api.com` free tier (or `open.er-api.com` as fallback)

3. Redis key pattern: `exchange_rates:{base}` → JSON string of rates
   - TTL: 25 hours
   - Store `fetched_at` timestamp with the data

4. Create REST endpoint:
   - `GET /api/v1/exchange-rates?base=KES&targets=USD,NGN` — public, no auth
   - Register in `app/api/v1/api.py`

5. The comparison dashboard endpoint (Task R-B5) calls this utility to convert venue response totals

**Acceptance criteria:**
- [ ] Rates cached in Redis with TTL
- [ ] Cache hit returns instantly
- [ ] Cache miss fetches from API and caches
- [ ] Conversion math is correct
- [ ] Public endpoint returns rates in correct format
- [ ] Handles API downtime gracefully (serve stale cache or return error)

---

## Task R-B10: GraphQL Schema Extensions

**Files to modify:**

- `app/graphql/types.py` — ADD new types
- `app/graphql/queries.py` — ADD RFP queries
- `app/graphql/mutations.py` — ADD RFP mutations
- `app/graphql/rfp_mutations.py` — NEW (mutation implementations)

**What to do:**

1. Add all new types from API contract section 3.2:
   - `RFPType`, `RFPAmenityType`, `RFPVenueType`, `VenueResponseType`, `ExtraCostAmenityType`
   - `ComparisonDashboardType`, `ComparisonVenueType`, `ComparisonBadgesType`
   - `ExchangeRateType`, `RFPListResult`
   - `VenueRFPInboxItem`, `VenueRFPDetail`, `VenueRFPInboxResult`
   - `PreSendVenueFit`, `PreSendSummary`

2. Add all queries from API contract section 3.3:
   - `organizationRFPs` — organizer's RFP list
   - `rfp` — single RFP detail
   - `rfpComparison` — comparison dashboard data
   - `rfpPreSendSummary` — pre-send fit indicators
   - `venueRFPInbox` — venue owner's inbox
   - `venueRFPDetail` — venue owner's RFP detail (marks as viewed)
   - `exchangeRates` — currency rates

3. Add all mutations from API contract section 3.4:
   - RFP management: `createRFP`, `updateRFP`, `deleteRFP`
   - Venue selection: `addVenuesToRFP`, `removeVenueFromRFP`
   - Actions: `sendRFP`, `extendRFPDeadline`, `closeRFP`, `duplicateRFP`
   - Decisions: `shortlistVenue`, `awardVenue`, `declineVenue`
   - Venue response: `submitVenueResponse`

4. Add input types: `RFPCreateInput`, `RFPUpdateInput`, `VenueResponseInput`, `ExtraCostAmenityInput`

5. Use DataLoaders for nested venue data on `RFPVenueType` (venue name, slug, etc.)

6. The `organizerName` field on `VenueRFPInboxItem` requires resolving `organization_id` → org name via cross-service call (same pattern as `listedBy` in Golden Directory — HTTP call to user-and-org-service with DataLoader caching)

**Acceptance criteria:**
- [ ] All GraphQL types match API contract section 3
- [ ] All queries work with proper auth
- [ ] All mutations enforce state machine
- [ ] DataLoaders prevent N+1 for venue data
- [ ] Cross-service org name resolution works
- [ ] Federation still works (existing schema unbroken)

---

## Execution Order

```
R-B1 (Models & Migration)
  ↓
R-B2 (Schemas)
  ↓
R-B3 (CRUD layer)
  ↓
R-B4 (Organizer endpoints)    R-B6 (Venue owner endpoints)    R-B9 (Exchange rates)
  ↓                              ↓                               ↓
R-B5 (Decisions + Compare) ←───┘───────────────────────────────┘
  ↓
R-B7 (Notifications)          R-B8 (Celery jobs)
  ↓                              ↓
R-B10 (GraphQL) ←───────────────┘
```

R-B4, R-B6, and R-B9 can be built in parallel once R-B1-R-B3 are done.
R-B7 and R-B8 can be built in parallel.
R-B10 should be last since it wraps all REST logic in GraphQL.
