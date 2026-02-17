# Venue Sourcing — Waitlist & Queue System: Backend Tasks

**Reference:** Read these before starting:
1. `VENUE_SOURCING_WAITLIST_SPEC.md` (root) — the approved feature specification
2. `venue-sourcing-docs/API_CONTRACT_WAITLIST.md` — the API contract (source of truth for types, endpoints, responses)
3. `venue-sourcing-docs/API_CONTRACT_RFP.md` — the RFP API contract (for integration points)

**Codebase:** `event-lifecycle-service/`

**Existing patterns to follow:**
- Models: `app/models/rfp.py`, `app/models/rfp_venue.py`, `app/models/venue_response.py`
- CRUD: `app/crud/crud_waitlist.py` (existing session waitlist — different feature, same pattern)
- Schemas: `app/schemas/waitlist.py` (existing session waitlist — different feature, same pattern)
- Routes: `app/api/v1/endpoints/` (follow RFP endpoint patterns)
- Background tasks: `app/background_tasks/waitlist_tasks.py` (existing), `app/scheduler.py`
- GraphQL: `app/graphql/types.py`, `app/graphql/mutations.py`, `app/graphql/queries.py`
- Notifications: `app/utils/kafka_helpers.py`, `app/core/email.py`

---

## Task Dependency Graph

```
W-B1 (Models & Migration)
  ├── W-B2 (Pydantic Schemas)
  │     └── W-B3 (CRUD Operations)
  │           ├── W-B4 (Organizer Waitlist Endpoints)
  │           ├── W-B5 (Venue Availability Endpoints)
  │           └── W-B6 (Signal Recording — RFP Integration)
  │                 └── W-B7 (Availability Inference Engine)
  ├── W-B8 (Background Jobs)  ← depends on W-B3
  └── W-B9 (Notification Service)  ← depends on W-B3
W-B10 (GraphQL) ← depends on W-B3, W-B4, W-B5
```

---

## W-B1: Models & Database Migration

**Create new model files and add fields to existing venue model.**

### New Files

**`app/models/venue_waitlist_entry.py`**

```python
# Fields from API Contract Section 1.1:
# id (vwl_ + 12hex), organization_id, venue_id, source_rfp_id, source_rfp_venue_id
# desired_dates_start, desired_dates_end, dates_flexible, attendance_min, attendance_max, event_type
# space_requirements (JSONB array of layout types from RFP)
# status (WaitlistStatus enum: waiting, offered, converted, expired, cancelled)
# hold_offered_at, hold_expires_at, hold_reminder_sent (default false)
# converted_rfp_id (nullable FK)
# cancellation_reason (nullable), cancellation_notes (nullable)
# expires_at, still_interested_sent_at (nullable), still_interested_responded (default false)
# created_at, updated_at
# NOTE: consecutive_no_responses is NOT a field — it is computed via get_consecutive_no_responses(venue_id)
```

Relationships:
- `venue` → Venue (many-to-one)
- `source_rfp` → RFP (many-to-one)
- `source_rfp_venue` → RFPVenue (many-to-one)
- `converted_rfp` → RFP (many-to-one, nullable)

Indexes:
- `ix_vwl_org_status` on (`organization_id`, `status`) — for organizer's waitlist dashboard
- `ix_vwl_venue_status` on (`venue_id`, `status`) — for cascade queries (find next waiting entry)
- `ix_vwl_hold_expires` on (`hold_expires_at`) WHERE status = 'offered' — for expiry job
- `ix_vwl_expires_at` on (`expires_at`) WHERE status = 'waiting' — for auto-expiry job
- Unique constraint: (`organization_id`, `venue_id`) WHERE status IN ('waiting', 'offered') — prevent duplicate active entries

**`app/models/venue_availability_signal.py`**

```python
# Fields from API Contract Section 1.2:
# id (vas_ + 12hex), venue_id, signal_type (SignalType enum), source_rfp_id (nullable),
# source_rfp_venue_id (nullable), signal_date (nullable), recorded_at, metadata (JSONB nullable)
```

Indexes:
- `ix_vas_venue_recorded` on (`venue_id`, `recorded_at`) — for inference queries (last 90 days)
- `ix_vas_venue_signal_type` on (`venue_id`, `signal_type`) — for signal counting

**No relationship back from Signal to other models** — this is an append-only audit log.

### Venue Model Changes

Add to `app/models/venue.py`:
```python
# Availability status (Tier 1)
availability_status = Column(String, nullable=False, server_default=text("'not_set'"))
availability_last_inferred_at = Column(DateTime(timezone=True), nullable=True)
availability_inferred_status = Column(String, nullable=True)
availability_manual_override_at = Column(DateTime(timezone=True), nullable=True)
```

### Migration

Create Alembic migration that:
1. Creates `venue_waitlist_entries` table
2. Creates `venue_availability_signals` table
3. Adds 4 columns to `venues` table
4. Creates all indexes listed above

### Register Models

Add imports to `app/models/__init__.py`:
```python
from app.models.venue_waitlist_entry import VenueWaitlistEntry
from app.models.venue_availability_signal import VenueAvailabilitySignal
```

---

## W-B2: Pydantic Schemas

**Create `app/schemas/venue_waitlist.py`**

Schemas needed (follow patterns in `app/schemas/waitlist.py`):

| Schema | Purpose |
|---|---|
| `WaitlistJoinRequest` | Request body for POST join waitlist (`source_rfp_venue_id: str`) |
| `WaitlistCancelRequest` | Request body for POST cancel (`reason: CancellationReason`, `notes: Optional[str]`) |
| `WaitlistEntryResponse` | Full waitlist entry response (all fields from API Contract Section 2.1) |
| `WaitlistEntryListResponse` | Paginated list with `waitlist_entries` and `pagination` |
| `WaitlistConversionResponse` | Conversion result with `waitlist_entry` and `new_rfp` |
| `VenueAvailabilityResponse` | Venue availability detail (API Contract Section 2.2) |
| `VenueAvailabilitySetRequest` | Request body for PUT availability (`availability_status: AvailabilityStatus`) |
| `AvailabilityBadgeResponse` | Public badge response (API Contract Section 2.3) |
| `AvailabilitySignalSummary` | Signal counts for the inference data |

Enums (define in schemas or a shared enums module):
- `WaitlistStatus`: `waiting`, `offered`, `converted`, `expired`, `cancelled`
- `CancellationReason`: `no_longer_needed`, `found_alternative`, `declined_offer`, `other`
- `AvailabilityStatus`: `accepting_events`, `limited_availability`, `fully_booked`, `seasonal`, `not_set`
- `SignalType`: `confirmed`, `tentative`, `unavailable`, `no_response`, `awarded`, `lost_to_competitor`, `rfp_cancelled`, `manual_available`, `manual_unavailable`

---

## W-B3: CRUD Operations

**Create `app/crud/crud_venue_waitlist.py`**

| Function | Description |
|---|---|
| `create_waitlist_entry(db, org_id, rfp_venue_id)` | Validates the RFPVenue has unavailable response, checks rate limit (5 active), checks no duplicate active entry for same venue, creates entry with context inherited from RFP. Computes `expires_at` (30 days after desired_dates_end, or 90 days if flexible). |
| `get_waitlist_entry(db, entry_id, org_id)` | Get single entry with org_id authorization check. |
| `list_waitlist_entries(db, org_id, status, active_only, page, page_size)` | Paginated list. If `active_only=True`, filter to `waiting` + `offered`. |
| `get_queue_position(db, entry)` | If entry status is terminal (`converted`, `expired`, `cancelled`), return null. Otherwise, count active entries (`waiting` or `offered`) for the same venue with `created_at` before this entry's `created_at`, plus 1. |
| `cancel_entry(db, entry_id, org_id, reason, notes)` | Validate state (`waiting` or `offered`), transition to `cancelled`, record reason. If was `offered`, trigger cascade. |
| `convert_hold(db, entry_id, org_id)` | Validate state (`offered`), validate hold not expired, **check RFP rate limit (max 5 active RFPs per org) — return 429 if exceeded**, clone source RFP (use existing duplicate logic), target only this venue, set `converted_rfp_id`, transition to `converted`. |
| `get_next_waiting_entry(db, venue_id)` | Find first entry with status=`waiting` for this venue, ordered by `created_at` ASC. |
| `offer_hold(db, entry)` | Set status=`offered`, `hold_offered_at`=now, `hold_expires_at`=now+48h. |
| `expire_hold(db, entry)` | Set status=`expired`. Increment consecutive_no_responses counter for the venue. |
| `get_consecutive_no_responses(db, venue_id)` | Count consecutive expired (non-cancelled) entries at the front of the queue. |
| `count_active_entries(db, org_id)` | Count entries with status in (`waiting`, `offered`) for rate limiting. |
| `resolve_circuit_breaker(db, venue_id)` | Validate venue has active circuit breaker (consecutive_no_responses >= 3). Reset counter to 0. Resume cascade by offering hold to next `waiting` entry. Emit Kafka event `waitlist.circuit_breaker_resolved`. |

**Create `app/crud/crud_venue_availability.py`**

| Function | Description |
|---|---|
| `get_venue_availability(db, venue_id)` | Return current status, override info, signal summary. |
| `set_venue_availability(db, venue_id, org_id, status)` | Validate venue ownership, set `availability_status`, `availability_manual_override_at`=now. If status=`accepting_events` and has waitlist entries, trigger cascade. |
| `clear_manual_override(db, venue_id, org_id)` | Clear `availability_manual_override_at`, revert to `availability_inferred_status`. |
| `record_signal(db, venue_id, signal_type, source_rfp_id, source_rfp_venue_id, signal_date, metadata)` | Append a new VenueAvailabilitySignal row. |
| `get_signal_summary(db, venue_id, days=90)` | Count signals by type for the last N days. Return summary with ratios. |
| `run_inference(db, venue_id)` | Run the inference algorithm (spec Section 5.2): compute unavailable_ratio, determine inferred_status. Store result. If manual override is NOT active and status improved, update displayed status and trigger cascade. |

---

## W-B4: Organizer Waitlist Endpoints

**Create `app/api/v1/endpoints/venue_waitlist.py`**

Routes (from API Contract Section 2.1):

| Method | Path | Handler |
|---|---|---|
| `POST` | `/api/v1/organizations/{orgId}/waitlists` | `join_waitlist` |
| `GET` | `/api/v1/organizations/{orgId}/waitlists` | `list_waitlist_entries` |
| `GET` | `/api/v1/organizations/{orgId}/waitlists/{waitlistId}` | `get_waitlist_entry` |
| `POST` | `/api/v1/organizations/{orgId}/waitlists/{waitlistId}/convert` | `convert_hold` |
| `POST` | `/api/v1/organizations/{orgId}/waitlists/{waitlistId}/cancel` | `cancel_entry` |

Auth: All endpoints require JWT with `org_id` matching path `orgId`.

Error handling:
- 429 for rate limit (5 active entries)
- 409 for duplicate active entry on same venue
- 409 for entry not in correct state
- 422 for hold already expired on convert attempt

**Register router in `app/api/v1/api.py`.**

---

## W-B5: Venue Availability Endpoints

**Create `app/api/v1/endpoints/venue_availability.py`**

Routes (from API Contract Sections 2.2 and 2.3):

| Method | Path | Handler | Auth |
|---|---|---|---|
| `GET` | `/api/v1/venues/{venueId}/availability` | `get_availability` | Venue owner |
| `PUT` | `/api/v1/venues/{venueId}/availability` | `set_availability` | Venue owner |
| `DELETE` | `/api/v1/venues/{venueId}/availability/override` | `clear_override` | Venue owner |
| `GET` | `/api/v1/venues/{venueId}/availability/status` | `get_availability_badge` | Public (no auth) |
| `POST` | `/api/v1/venues/{venueId}/waitlist-circuit-breaker/resolve` | `resolve_circuit_breaker` | Venue owner |

The public badge endpoint should use Redis caching (5-minute TTL) to avoid database hits on every directory listing.

The circuit breaker resolution endpoint resets the consecutive no-response counter for the venue and resumes the waitlist cascade. Only callable when the venue has an active circuit breaker pause.

**Register router in `app/api/v1/api.py`.**

---

## W-B6: Signal Recording — RFP Integration

**This is the critical integration task.** Modify existing RFP code to record availability signals on key lifecycle events.

### Files to modify:

1. **Venue response submission** (where `submitVenueResponse` / `POST .../respond` is handled):
   - After saving the response, call `record_signal(venue_id, signal_type=response.availability, source_rfp_id, source_rfp_venue_id, signal_date=rfp.preferred_dates_start)`

2. **RFP deadline processing** (existing background job that marks `no_response`):
   - For each venue marked `no_response`, call `record_signal(venue_id, "no_response", ...)`

3. **Award venue** (where `awardVenue` / `POST .../award` is handled):
   - For the awarded venue: `record_signal(venue_id, "awarded", ...)`
   - For all other responded/shortlisted venues on the same RFP: `record_signal(venue_id, "lost_to_competitor", ...)`

4. **Close/cancel RFP** (where `closeRFP` / `POST .../close` is handled):
   - For all targeted venues: `record_signal(venue_id, "rfp_cancelled", ...)`

5. **Venue availability manual set** (new endpoint in W-B5):
   - `record_signal(venue_id, "manual_available" or "manual_unavailable", source_rfp_id=None, ...)`

### Important: Do NOT break existing RFP functionality
- Signal recording should be a non-blocking side effect
- Wrap in try/except — if signal recording fails, the RFP operation must still succeed
- Log failures for monitoring

---

## W-B7: Availability Inference Engine

**Create `app/utils/venue_availability_inference.py`**

Implements the inference algorithm from the spec (Section 5.2):

```python
def run_inference_for_venue(db: Session, venue_id: str) -> Optional[str]:
    """
    Run availability inference for a single venue.
    Returns the inferred status or None if insufficient data.

    Algorithm:
    1. Query signals from last 90 days (signal_type in confirmed, tentative, unavailable)
    2. If no signals: return "not_set"
    3. Calculate unavailable_ratio = unavailable_count / total
    4. If ratio >= 0.8: "fully_booked"
    5. If ratio >= 0.5: "limited_availability"
    6. Else: "accepting_events"

    Never infer "seasonal" — manual only.
    """

def run_inference_all(db: Session) -> dict:
    """
    Run inference for all venues with recent signals.
    Called by the periodic background job.

    Returns dict of {venue_id: (old_status, new_status)} for venues that changed.
    For each venue where status improved AND manual override is NOT active:
      - Update venue.availability_status
      - Update venue.availability_last_inferred_at
      - Update venue.availability_inferred_status
      - Check if venue has waitlist entries → trigger cascade
    """
```

---

## W-B8: Background Jobs

**Create `app/background_tasks/venue_waitlist_tasks.py`**

| Function | Schedule | Description |
|---|---|---|
| `process_hold_expiry()` | Every 1 minute | Find entries where `status='offered'` AND `hold_expires_at < now()`. For each: expire, increment consecutive_no_responses, trigger cascade. If consecutive_no_responses >= 3, activate circuit breaker instead. |
| `send_hold_reminders()` | Every 15 minutes | Find entries where `status='offered'` AND `hold_expires_at - now() < 24h` AND `hold_reminder_sent=False`. Send reminder notification, set `hold_reminder_sent=True`. |
| `process_auto_expiry()` | Every 1 hour | Find entries where `status='waiting'` AND `expires_at < now()`. Transition to `expired`. |
| `send_still_interested_nudges()` | Daily at 10:00 UTC | Find entries where `status='waiting'` AND `dates_flexible=True` AND `created_at + 60 days < now()` AND `still_interested_sent_at IS NULL`. Send nudge, set `still_interested_sent_at`. |
| `process_nudge_expiry()` | Daily at 10:00 UTC | Find entries where `still_interested_sent_at + 7 days < now()` AND `still_interested_responded=False`. Auto-expire them. |
| `run_availability_inference()` | Every 6 hours | Call `run_inference_all()` from W-B7. |
| `process_circuit_breaker_expiry()` | Daily at 00:00 UTC | Find venues where circuit breaker was triggered 7+ days ago and venue owner didn't respond. Deactivate those waitlists. |

**Register all jobs in `app/scheduler.py`** — add to the `init_scheduler()` function following the existing pattern (IntervalTrigger / CronTrigger).

---

## W-B9: Notification Service

**Create `app/utils/venue_waitlist_notifications.py`**

Implement notification dispatchers for each event in the API Contract Section 4:

| Function | Channels | Template |
|---|---|---|
| `notify_waitlist_joined(entry)` | In-app + Email | Confirmation with queue position |
| `notify_hold_offered(entry)` | In-app + Email + WhatsApp | WhatsApp template `waitlist_hold_offered` |
| `notify_hold_reminder(entry)` | Email + WhatsApp | WhatsApp template `waitlist_hold_reminder` |
| `notify_hold_expired(entry)` | In-app + Email | Hold expired, removed from queue |
| `notify_converted(entry)` | In-app | New RFP created, link to it |
| `notify_position_changed(entry, new_position)` | In-app | Position improved |
| `notify_still_interested(entry)` | Email | 60-day nudge with action link |
| `notify_auto_expired(entry)` | In-app + Email | Entry expired due to time |
| `notify_circuit_breaker(venue_id)` | In-app + Email (venue owner) | 3 no-responses, confirm to continue |

**Kafka events:** Each notification function should also emit a Kafka event via `kafka_helpers.py` following the schema in API Contract Section 6.

**Email templates:** Follow existing patterns in `app/core/email.py` and `app/utils/waitlist_emails.py`.

---

## W-B10: GraphQL Layer

**Create `app/graphql/venue_waitlist_types.py`**

Types from API Contract Section 3.2:
- `VenueWaitlistEntryType`
- `WaitlistEntryListResult`
- `WaitlistConversionResult`
- `VenueAvailabilityType`
- `AvailabilitySignalSummary`
- `AvailabilityBadge`

Enums from API Contract Section 3.1:
- `WaitlistStatus`
- `CancellationReason`
- `AvailabilityStatus`
- `SignalType`

**Create `app/graphql/venue_waitlist_queries.py`**

Queries from API Contract Section 3.4:
- `myWaitlistEntries(status, activeOnly, page, pageSize)` → calls CRUD list
- `waitlistEntry(id)` → calls CRUD get
- `venueAvailability(venueId)` → calls CRUD get_venue_availability (auth: venue owner)
- `venueAvailabilityBadge(venueId)` → public, returns badge with color/label

**Create `app/graphql/venue_waitlist_mutations.py`**

Mutations from API Contract Section 3.5:
- `joinVenueWaitlist(sourceRfpVenueId)` → calls CRUD create_waitlist_entry
- `convertWaitlistHold(waitlistId)` → calls CRUD convert_hold
- `cancelWaitlistEntry(waitlistId, reason, notes)` → calls CRUD cancel_entry
- `respondStillInterested(waitlistId, interested)` → if interested=True, reset `still_interested_sent_at` to null and set `still_interested_responded=true`. If False, cancel entry with `cancellation_reason='nudge_declined'`.
- `setVenueAvailability(venueId, status)` → calls CRUD set_venue_availability
- `clearVenueAvailabilityOverride(venueId)` → calls CRUD clear_manual_override
- `resolveWaitlistCircuitBreaker(venueId)` → calls CRUD resolve_circuit_breaker

**Extend existing venue types:**

Add `availabilityStatus`, `availabilityBadgeColor`, `availabilityBadgeLabel` resolved fields to `VenueType` and `VenueFullType` in `app/graphql/types.py` (API Contract Section 3.3).

**Register** all new queries and mutations in the main GraphQL schema (`app/graphql/queries.py`, `app/graphql/mutations.py`).

---

## Verification Checklist

After implementation, verify:

- [ ] Alembic migration runs cleanly (upgrade and downgrade)
- [ ] Joining waitlist inherits all context from RFP (no manual input needed)
- [ ] Rate limit (5 active entries) is enforced
- [ ] Duplicate active entry for same venue is blocked
- [ ] Hold conversion creates a properly pre-filled draft RFP with only the waitlisted venue
- [ ] Hold expiry cascades to next person in FIFO order
- [ ] Circuit breaker fires after 3 consecutive no-responses
- [ ] Signal recording in RFP endpoints doesn't break existing RFP functionality
- [ ] Inference engine correctly computes availability from signals
- [ ] Manual override takes precedence over inference
- [ ] Cascade triggers on both inference improvement and manual override
- [ ] All Kafka events are emitted for state transitions
- [ ] Queue position is calculated correctly and updates when people ahead leave
- [ ] Auto-expiry works for both date-specific (30 days) and general (90 days) entries
- [ ] "Still interested?" nudge is sent at 60 days, auto-expire at 67 days if no response
- [ ] Availability badge is included in venue list/detail GraphQL responses
- [ ] Public availability badge endpoint is cached
