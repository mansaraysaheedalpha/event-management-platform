# Venue Sourcing — Waitlist & Queue System Specification

**Phase 1, Section 3: Waitlist & Queue System**
**Date:** February 2026
**Status:** Approved (Feb 2026)
**Depends on:** Golden Directory (Phase 1, Section 1) + Standardized RFP (Phase 1, Section 2) — both must be live

---

## 1. Overview

The Waitlist & Queue System allows event organizers to join a FIFO queue when their preferred venue is unavailable. Instead of walking away after an RFP response of "unavailable," the organizer can express continued interest and be automatically notified — with an exclusive time-limited hold — if the venue becomes available.

This is the third and final building block of the manual venue sourcing pipeline. The Golden Directory provides the data, the RFP system provides the workflow, and the Waitlist system provides persistence — ensuring no demand signal is lost.

**Key design principles:**
- **Post-RFP only at launch** — waitlists are a natural extension of the RFP conversation, not a standalone feature
- **FIFO fairness** — first in line gets first chance, with exclusive time-limited holds
- **Signal-driven availability** — venue availability is inferred from RFP response patterns, reducing manual work for venue owners
- **Queue depth hidden from venues** — prevents off-platform poaching in relationship-driven African markets

---

## 2. How It Works

### Step 1: Organizer Joins the Waitlist (Post-RFP)

**Entry point:** The comparison dashboard or RFP detail page, when a venue's response has `availability: unavailable`.

The organizer sees a **"Join Waitlist"** button next to any venue that responded as unavailable. Clicking it:

1. Creates a waitlist entry with all context inherited from the RFP:
   - Desired dates (from the RFP's `preferred_dates_start` / `preferred_dates_end`)
   - Attendance range (from the RFP's `attendance_min` / `attendance_max`)
   - Space requirements (from the RFP)
   - The source RFP ID and RFPVenue ID (for audit trail)
2. Shows the organizer their **queue position**: "You are #3 in line for [Venue Name]"
3. Sends a confirmation notification to the organizer

**No additional form is needed** — all relevant context already exists in the RFP. The organizer just clicks "Join Waitlist" and they're in the queue.

**Rate limit:** Maximum **5 active waitlist entries per organizer**. Active = `waiting` or `offered` state. This prevents position hoarding across venues. If an organizer consistently hits the cap, it can be raised for premium accounts later.

### Step 2: Queue Management (FIFO)

Waitlist entries are ordered by `created_at` timestamp — strict FIFO. No priority bumping, no premium queue jumping at launch.

**Queue position** is calculated dynamically: count of active entries (`waiting` or `offered`) for the same venue that were created before the current entry, plus one. This is displayed to the organizer on their waitlist dashboard.

### Step 3: Venue Becomes Available (Signal-Driven)

Availability changes are detected through two mechanisms:

**Mechanism A — Signal-Driven Inference (Primary):**
The system continuously analyzes RFP response patterns to infer venue availability. See Section 5 for the full inference engine specification.

When the inference engine detects a venue transitioning from `fully_booked` or `limited_availability` to `accepting_events`, it triggers the waitlist cascade for that venue.

**Mechanism B — Manual Override (Secondary):**
Venue owners can manually update their availability status at any time through their venue dashboard. If a venue owner sets status to `accepting_events` and there are entries in the waitlist queue, the cascade triggers.

**Mechanism C — RFP Cancellation / Award Elsewhere:**
When an organizer closes an RFP or awards it to a different venue, the "losing" venues may now have freed-up capacity. The system records this as an availability signal.

### Step 4: Exclusive Hold Offered (48 Hours)

When a venue becomes available and has a non-empty waitlist queue:

1. The **first person in the FIFO queue** receives an exclusive hold offer
2. They are notified via **In-app + Email + WhatsApp** (high priority)
3. The hold clock starts immediately: **48 hours to act**
4. During the hold period, no other waitlist entry for this venue is offered

**What "acting on the hold" means:** The organizer creates a new RFP pre-filled with their original RFP's data, targeted at only this one venue. The hold guarantees the venue will respond — it does not lock in old pricing. This is Option A (fresh single-venue RFP), chosen because original pricing may be stale after weeks/months on a waitlist.

The organizer can:
- **Convert** — creates the pre-filled RFP → waitlist entry transitions to `converted`
- **Cancel** — explicitly passes → waitlist entry transitions to `cancelled`, cascade to next person
- **Do nothing** — hold expires after 48 hours → waitlist entry transitions to `expired`, cascade to next person

### Step 5: Cascade

When a hold expires or is cancelled:

1. The next person in the FIFO queue receives the hold offer
2. Same 48-hour clock, same notification channels
3. Process repeats until someone converts or the queue empties

**Circuit Breaker:** After **3 consecutive expirations with no response** (not cancellations — specifically no response at all), the cascade **pauses** and the system:
- Notifies the venue owner: "Your waitlist for [date context] has had 3 unresponsive entries. Would you like to keep it active?"
- If the venue owner confirms → cascade resumes with the 4th person
- If the venue owner doesn't respond within 7 days → waitlist is deactivated for that venue until the owner manually reactivates
- This prevents zombie queues churning through people with broken notification channels or stale contact info

### Step 6: Waitlist Expiry

Waitlist entries do not persist forever. Auto-expiry rules:

| Scenario | Expiry Rule |
|---|---|
| **Date-specific entry** (RFP had specific dates) | 30 days after the desired event date passes |
| **General entry** (RFP had flexible dates) | 90 days after creation |
| **"Still interested?" nudge** | Sent at 60 days for general entries |

When a "still interested?" notification goes unanswered for 7 days, the entry auto-expires and the queue compacts.

---

## 3. State Machine

### 3.1 Waitlist Entry States

| State | Description | Transitions To |
|---|---|---|
| `waiting` | In the FIFO queue, no hold offered yet | `offered`, `cancelled`, `expired` |
| `offered` | Exclusive hold offered, 48-hour clock ticking | `converted`, `cancelled`, `expired` |
| `converted` | Organizer acted on hold — created new RFP | (terminal) |
| `expired` | Hold expired without action, OR entry auto-expired due to date/time rules | (terminal) |
| `cancelled` | Organizer voluntarily left the queue or explicitly declined the hold | (terminal) |

**5 states total.** Clean, minimal, auditable.

**`cancelled` reason tracking:** The `cancellation_reason` field captures why:

| Reason | Description |
|---|---|
| `no_longer_needed` | Organizer no longer needs a venue |
| `found_alternative` | Organizer booked elsewhere |
| `declined_offer` | Organizer explicitly declined the hold offer |
| `nudge_declined` | Organizer responded "not interested" to 60-day nudge |
| `other` | Free text reason |

This preserves analytics granularity without adding extra states.

**Automatic transitions:**
- `waiting` → `offered`: when this entry reaches the front of the queue and venue becomes available
- `offered` → `expired`: when 48-hour hold clock runs out (APScheduler scheduled task)
- `waiting` → `expired`: when auto-expiry rules trigger (date passed + 30 days, or 90 days general)

---

## 4. Venue Availability Status (Tier 1 — Launch)

Every venue in the Golden Directory gets a new **availability status badge** displayed on directory listings and venue detail pages.

### 4.1 Status Values

| Status | Badge Color | Description |
|---|---|---|
| `accepting_events` | Green | Venue is actively taking bookings |
| `limited_availability` | Yellow | Some dates/spaces still open, but filling up |
| `fully_booked` | Red | No availability for the foreseeable future |
| `seasonal` | Blue | Venue operates seasonally (e.g., outdoor venues) |
| `not_set` | Gray | No availability data yet (default for new venues) |

### 4.2 How Status Is Set

**Two mechanisms, working together:**

1. **Signal-driven inference** (Section 5) — the primary mechanism. Automatically computes status based on RFP response patterns. Zero effort for venue owners.

2. **Manual override** — venue owners can set their status at any time via their venue dashboard. The manual override always takes precedence over inference. A `manual_override_at` timestamp tracks when this was last done.

**Priority rule:** If `manual_override_at` is more recent than `last_inferred_at`, the manual status wins. If a new inference runs after the manual override, the inference result is stored but does **not** overwrite the manual status. The venue owner must explicitly clear their override to return to inference-driven status.

### 4.3 Display Rules

- **Golden Directory listing cards:** Small colored dot + text label (e.g., 🟢 Accepting Events)
- **Venue detail page:** Badge in the header area
- **RFP venue selection:** Shown alongside capacity fit and amenity match during pre-send summary
- **Venues with `not_set` status:** Show gray "Status unknown" — does not block RFP sending

> **Tier 2 (Post-Launch):** Date-specific availability calendar. Venue owners or the inference engine can mark specific date ranges as available/unavailable. This enables date-aware waitlists and smarter RFP targeting. Deferred because it requires significant frontend effort and venue adoption of calendar management.

---

## 5. Signal-Driven Availability Inference Engine

The standout feature of this system. Instead of asking venue owners to maintain availability calendars (which they won't do consistently, especially in African markets), the platform **infers** availability from RFP response behavior.

### 5.1 Signals Collected

Every RFP response generates a signal:

| Signal | Source | Weight |
|---|---|---|
| Venue responded `confirmed` | VenueResponse.availability | Positive — venue has capacity |
| Venue responded `tentative` | VenueResponse.availability | Weak positive — venue may have capacity |
| Venue responded `unavailable` | VenueResponse.availability | Negative — venue is booked |
| Venue did not respond (no_response) | RFPVenue.status after deadline | Neutral — could be disengaged, not necessarily booked |
| RFP awarded to this venue | RFPVenue.status = awarded | Strong negative — venue just took a booking |
| RFP awarded elsewhere (this venue declined) | RFPVenue.status = declined after another awarded | Weak positive — venue's slot freed up |
| Organizer closed/cancelled RFP | RFP.status = closed | Weak positive for all targeted venues |

### 5.2 Inference Logic

The inference engine runs as a **APScheduler periodic task** (every 6 hours) and processes signals from the last 90 days.

**Algorithm (per venue):**

```
recent_responses = responses in last 90 days
if no recent_responses:
    inferred_status = "not_set"
    return

unavailable_count = count where availability = "unavailable"
confirmed_count = count where availability = "confirmed"
tentative_count = count where availability = "tentative"
total_responses = unavailable_count + confirmed_count + tentative_count

unavailable_ratio = unavailable_count / total_responses

if unavailable_ratio >= 0.8:
    inferred_status = "fully_booked"
elif unavailable_ratio >= 0.5:
    inferred_status = "limited_availability"
else:
    inferred_status = "accepting_events"
```

**Notes:**
- `no_response` entries are excluded from the calculation (they indicate disengagement, not availability)
- The `seasonal` status is **never inferred** — it can only be set manually by the venue owner
- The engine stores the inferred status, the signal counts, and a `last_inferred_at` timestamp
- If manual override is active (see Section 4.2), the inferred result is stored but does not change the displayed status

### 5.3 Venue Availability Signals Table

Every signal is persisted for auditability and for the Phase 2 AI layer:

```
VenueAvailabilitySignal {
  id:                 string       // "vas_" + 12hex
  venue_id:           string       // FK to Venue
  signal_type:        enum         // "confirmed" | "tentative" | "unavailable" | "no_response" | "awarded" | "lost_to_competitor" | "rfp_cancelled" | "manual_available" | "manual_unavailable"
  source_rfp_id:      string?      // FK to RFP (nullable — manual signals have no source RFP)
  source_rfp_venue_id: string?     // FK to RFPVenue
  signal_date:        date?        // the date this signal applies to (from RFP preferred dates, nullable for manual signals)
  recorded_at:        datetime     // when the signal was recorded
  metadata:           json?        // additional context (e.g., attendance size, event type)
}
```

This table is **append-only** — signals are never updated or deleted. The inference engine reads from it; RFP response events write to it.

### 5.4 Waitlist Cascade Trigger

The inference engine does **not** directly trigger waitlist cascades. Instead:

1. Inference runs → computes new status for a venue
2. If the new status is **more available** than the previous status (e.g., `fully_booked` → `limited_availability`, or `limited_availability` → `accepting_events`):
   - Check if this venue has any `waiting` entries in the waitlist queue
   - If yes → trigger the cascade (offer hold to first person in FIFO)
3. If the new status is **less available** or unchanged → no cascade action

**Manual override also triggers cascade:** If a venue owner manually sets status to `accepting_events` and there are waitlist entries, the cascade triggers immediately.

---

## 6. Notification Strategy

### 6.1 Notification Events

| Event | Recipient | Channels | Priority |
|---|---|---|---|
| Waitlist joined confirmation | Organizer | In-app + Email | Medium |
| Hold offered (your turn!) | Organizer | In-app + Email + WhatsApp | High |
| Hold reminder (24h before expiry) | Organizer | Email + WhatsApp | High |
| Hold expired (no action taken) | Organizer | In-app + Email | Medium |
| Entry auto-expired (date/time limit) | Organizer | In-app + Email | Medium |
| Waitlist converted (RFP created) | Organizer | In-app | Low |
| Queue position changed | Organizer | In-app | Low |
| "Still interested?" nudge (60 days) | Organizer | Email | Medium |
| Circuit breaker — confirm waitlist active | Venue owner | In-app + Email | Medium |
| Circuit breaker resolved | Venue owner | In-app | Low |

### 6.2 WhatsApp Templates

**Template 5: `waitlist_hold_offered`** (High priority)
```
Hi {{1}},

Great news! {{2}} is now available for your event "{{3}}".

You have an exclusive 48-hour hold. Act now to secure your booking.

Claim your spot: {{4}}

Hold expires: {{5}}
```
Variables: `{organizer_name}`, `{venue_name}`, `{original_rfp_title}`, `{dashboard_deep_link}`, `{hold_expiry_datetime}`

**Template 6: `waitlist_hold_reminder`** (High priority)
```
Hi {{1}},

Reminder: Your exclusive hold on {{2}} expires in {{3}}.

Don't miss out — claim your spot now: {{4}}
```
Variables: `{organizer_name}`, `{venue_name}`, `{hours_remaining}`, `{dashboard_deep_link}`

> **Action item:** Submit these templates for WhatsApp approval alongside the RFP templates. Bundle the approval request.

---

## 7. Pages (Frontend)

### 7.1 Organizer Pages

| Route | Description |
|---|---|
| `/platform/waitlists` | Waitlist dashboard — all organizer's active and past waitlist entries with queue position, status, hold timers |
| `/platform/waitlists/[id]` | Waitlist entry detail — venue info, queue position, hold status, action buttons (convert/cancel) |

### 7.2 Integration Points

| Location | What Changes |
|---|---|
| **Comparison Dashboard** (`/platform/rfps/[id]/compare`) | "Join Waitlist" button on venues with `availability: unavailable` |
| **RFP Detail** (`/platform/rfps/[id]`) | "Join Waitlist" link next to unavailable venues in the venue list |
| **Golden Directory Cards** (`/venues`) | Availability status badge (green/yellow/red/blue/gray dot + label) |
| **Venue Detail Page** (`/venues/[slug]`) | Availability status badge in header |
| **Venue Dashboard** (`/platform/venues/[venueId]`) | Manual availability status toggle |
| **RFP Pre-Send Summary** | Availability status shown alongside capacity fit and amenity match |

### 7.3 Waitlist Dashboard Features

The organizer's `/platform/waitlists` page shows:

| Column | Description |
|---|---|
| Venue Name | With availability badge |
| Queue Position | "#3 in line" — dynamically calculated |
| Status | waiting / offered / converted / expired / cancelled |
| Hold Timer | Countdown if in `offered` state (e.g., "23h 14m remaining") |
| Source RFP | Link to the original RFP that triggered the waitlist join |
| Desired Dates | From original RFP |
| Joined At | When they joined the queue |
| Actions | "Cancel" (if waiting), "Convert" / "Pass" (if offered) |

---

## 8. Scope Boundaries

### What's IN at launch:
- Post-RFP waitlist join (comparison dashboard trigger)
- FIFO queue with exclusive 48-hour holds
- 5-state machine (waiting, offered, converted, expired, cancelled)
- Automatic cascade with circuit breaker (3 consecutive no-responses)
- Venue availability badge (Tier 1 — 5 statuses)
- Signal-driven availability inference from RFP responses
- Manual availability override for venue owners
- Waitlist entry auto-expiry (30 days post-event-date / 90 days general)
- Queue position display for organizers
- Conversion via pre-filled single-venue RFP
- Max 5 active waitlist entries per organizer
- Venue-level queues only (not space-level)
- Queue depth hidden from venues
- Kafka events for all state transitions
- WhatsApp notifications for high-priority events

### What's OUT at launch (fast-follow / Phase 2):
- Direct directory waitlists (join waitlist from venue page without prior RFP)
- Date-specific availability calendar (Tier 2)
- Space-level queues (per-room waitlists)
- Queue depth visible to venues (revisit when platform lock-in is sufficient)
- Premium queue features (priority, relaxed limits)
- AI-powered availability prediction
- Aggregate waitlist inbox for multi-venue operators

---

## 9. Technical Approach

- **Backend:** Extends event-lifecycle-service (same service as Golden Directory and RFP). New models: WaitlistEntry, VenueAvailabilitySignal. New field on Venue: `availability_status`, `availability_manual_override_at`, `availability_last_inferred_at`
- **Background jobs:** APScheduler periodic tasks (matching existing pattern in `scheduler.py`) for hold expiry processing, cascade execution, availability inference, "still interested?" nudges, entry auto-expiry
- **Notifications:** Same channel-agnostic event system as RFP → Email (Resend), WhatsApp (Africa's Talking), In-app
- **Events:** Kafka events for all waitlist state transitions (`waitlist.joined`, `waitlist.hold_offered`, `waitlist.hold_expired`, `waitlist.auto_expired`, `waitlist.converted`, `waitlist.cancelled`, `waitlist.circuit_breaker_triggered`, `waitlist.circuit_breaker_resolved`, `venue.availability_inferred`, `venue.availability_manual_set`)
- **Real-time:** At launch, polling (30-second interval) for hold timer and queue position updates. Post-launch, migrate to Socket.IO events for true real-time updates (`waitlist.hold_expired`, `waitlist.position_changed`)
- **API:** REST + GraphQL endpoints following existing patterns
- **Conversion flow:** Reuses the existing "Duplicate RFP" infrastructure — creates a new draft RFP pre-filled from the source RFP, targeted at only the waitlisted venue

---

## 10. Resolved Questions

| Question | Decision | Rationale |
|---|---|---|
| **Space-level vs venue-level queues?** | **Venue-level only** | Organizers request space *types* in RFPs, not specific rooms. The venue decides which space to offer. Space-level queues multiply complexity without user value at launch. |
| **Overlapping date ranges?** | **Simple overlap check** | At Tier 1 (general status badge), waitlists aren't date-specific. At Tier 2, check for any overlap between availability and desired dates, offer holds in FIFO order, let humans negotiate exact dates during the hold period. |
| **Queue depth visible to venues?** | **No** | In African markets, venues seeing high demand might contact organizers directly, bypassing the platform. Queue depth stays hidden until platform lock-in justifies transparency. Venues are notified only when a hold is accepted (conversion). |
| **State machine complexity?** | **5 states, not 7** | Merged `hold_offered`/`hold_active` into `offered` (48h clock starts on send). Merged `passed` into `cancelled` with `cancellation_reason` enum. |
| **What does "conversion" mean?** | **New pre-filled single-venue RFP** | Original pricing may be stale. A fresh RFP ensures current terms. The hold guarantees venue engagement, not old pricing. |
| **Waitlist entry lifespan?** | **30 days post-event-date / 90 days general** | Prevents queue rot. "Still interested?" nudge at 60 days for general entries. |
| **Rate limit?** | **Max 5 active entries per organizer** | Waitlist entries are long-lived commitments, unlike one-shot RFPs. 5 is sufficient; can raise for premium accounts. |
| **Circuit breaker threshold?** | **3 consecutive no-responses** | Pauses cascade, notifies venue owner. Prevents zombie queues. |

---

## 11. What This Enables Next

- **Phase 2 (AI Layer):** Smart waitlist — AI monitors venue signals and proactively suggests when to join waitlists. Autonomous closer can auto-convert holds when confidence is high. Predictive availability uses signal history to forecast when venues will likely have openings.
- **Tier 2 Calendar:** Date-specific availability enables smarter waitlist matching — only notify organizers whose desired dates actually overlap with newly opened slots.
- **Direct Directory Waitlists:** Once Tier 2 calendar exists, organizers can join waitlists directly from venue pages for specific dates without creating an RFP first.

---

## 12. Fast-Follow Backlog

1. **Direct directory waitlists** — join from venue page without prior RFP (requires Tier 2 calendar)
2. **Tier 2 date-specific calendar** — venue-level and eventually space-level date management
3. **Aggregate waitlist view for venues** — "You have 12 waitlisted organizers across your 3 venues"
4. **Premium queue features** — raised limits, priority positioning for paid accounts
5. **Queue depth visibility for venues** — revisit when platform lock-in is sufficient
6. **Waitlist analytics dashboard** — conversion rates, average wait times, popular venues
