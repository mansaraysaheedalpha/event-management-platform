# Capacity Management Tracker

Reference file for tracking capacity-related gaps across the platform.
Items are ordered by severity.

---

## Status Legend
- DONE — Fully implemented and enforced
- PARTIAL — Model/schema exists but enforcement is incomplete
- MISSING — Feature does not exist at all
- PLANNED — Design documented, ready for implementation

---

## 1. Ticket Quantity Decrement on Purchase
**Status:** DONE | **Severity:** N/A

**Fixed** in commit `f72b716`:
- `is_available()` now includes `quantity_reserved` in availability check
- Reserve inventory when checkout session is created (prevents overselling)
- Release reservation on order cancel, expire, and webhook cancel
- `increment_quantity_sold()` also decrements `quantity_reserved`
- Added `reserve_quantity()` and `release_quantity()` to ticket type CRUD

---

## 2. Max Concurrent Viewers (Virtual Events)
**Status:** MISSING | **Severity:** CRITICAL

**Problem:** `virtual_settings` JSONB on Event model stores `max_concurrent_viewers` but there is **zero enforcement**. No viewer tracking, no Redis counter, no rejection logic.

**Files:**
- `event-lifecycle-service/app/models/event.py` — virtual_settings column (line ~49)
- `real-time-service/src/live/streaming/streaming.gateway.ts` — minimal gateway (only broadcasts subtitles)

**What Needs to Happen:**
- [ ] Track concurrent viewers via Redis counter (INCR on join, DECR on leave/disconnect)
- [ ] Check counter against `max_concurrent_viewers` before allowing stream join
- [ ] Return error when viewer limit reached
- [ ] Handle disconnects (WebSocket close / heartbeat timeout) to decrement counter

---

## 3. Session Join Enforcement (Virtual)
**Status:** DONE | **Severity:** N/A

**Fixed** in commit `100c1de`:
- `joinVirtualSession` mutation now checks both `session_capacity` table and `session.max_participants` before allowing join
- Returns "session is full" with waitlist redirect when at capacity
- `leaveVirtualSession` decrements the capacity counter on leave
- UI: "Max Participants" input added to session create/edit modals

**Note:** This only works for virtual sessions. In-person session capacity requires the Session RSVP system (see item #5).

---

## 4. Expo Booth Visitor Capacity
**Status:** MISSING | **Severity:** MEDIUM

**Problem:** `ExpoBooth` model has tier system and chat/video flags but **no capacity field, no visitor tracking, no limiting logic**.

**Files:**
- `event-lifecycle-service/app/models/expo_booth.py` — booth model

**What Needs to Happen:**
- [ ] Add `max_visitors` column to expo_booth table
- [ ] Track active visitors (join/leave)
- [ ] Enforce limit before allowing booth entry

---

## 5. Session RSVP / Booking System (In-Person Capacity)
**Status:** PLANNED | **Severity:** HIGH

**Problem:** There is no way for attendees to RSVP for individual sessions. Users register for the event as a whole. For in-person events, `max_participants` on sessions is purely informational — there's no user action to enforce it against. People just walk into rooms.

**Current State:**
- `Session` model has `max_participants` field (nullable)
- `SessionCapacity` table exists with `maximum_capacity` / `current_attendance`
- Waitlist system exists for sessions
- Virtual sessions enforce capacity at join time (`joinVirtualSession`)
- In-person sessions have **zero enforcement**

**Implementation Plan:**

### Backend (event-lifecycle-service)

**Step 1: Session RSVP Model**
- Create `session_rsvps` table:
  - `id` (PK, `srsvp_{uuid}`)
  - `session_id` (FK → sessions)
  - `user_id` (string, not null)
  - `event_id` (FK → events)
  - `status` (CONFIRMED, CANCELLED, WAITLISTED)
  - `rsvp_at` (timestamp)
  - `cancelled_at` (timestamp, nullable)
  - Unique constraint on `(session_id, user_id)`
- Alembic migration for the new table

**Step 2: CRUD Operations**
- Create `crud_session_rsvp.py`:
  - `create_rsvp(db, session_id, user_id, event_id)` — create RSVP
  - `cancel_rsvp(db, session_id, user_id)` — cancel RSVP
  - `get_user_rsvp(db, session_id, user_id)` — check if user already RSVPed
  - `get_rsvps_by_session(db, session_id)` — list RSVPs
  - `get_rsvps_by_user(db, user_id, event_id)` — user's schedule
  - `get_rsvp_count(db, session_id)` — count for capacity check

**Step 3: GraphQL Mutations**
- `rsvpToSession(sessionId)`:
  1. Verify user is authenticated
  2. Verify user is registered for the event
  3. Check if already RSVPed (idempotent — return existing)
  4. Check capacity: count RSVPs vs `max_participants` (or `session_capacity.maximum_capacity`)
  5. If full → return error "Session is full" (or auto-add to waitlist if waitlist enabled)
  6. Create RSVP record
  7. Increment `session_capacity.current_attendance`
  8. Return success with RSVP details
- `cancelSessionRsvp(sessionId)`:
  1. Find and cancel RSVP
  2. Decrement `session_capacity.current_attendance`
  3. If waitlist has people → auto-send offer to next in line
  4. Return success
- `getMySchedule(eventId)`:
  1. Return all sessions user has RSVPed for
  2. Include session details for rendering a personal schedule view

**Step 4: GraphQL Queries & Types**
- Add `SessionRsvpType` (id, sessionId, userId, status, rsvpAt)
- Add `isRsvped: Boolean` resolver on `SessionType` (checks if current user has RSVP)
- Add `rsvpCount: Int` resolver on `SessionType`
- Add `availableSpots: Int` and `isFull: Boolean` resolvers on `SessionType`
- Add `mySchedule(eventId)` query returning list of RSVPed sessions

### Frontend (globalconnect)

**Step 5: GraphQL Operations**
- Add `RSVP_TO_SESSION_MUTATION`
- Add `CANCEL_SESSION_RSVP_MUTATION`
- Add `GET_MY_SCHEDULE_QUERY`
- Update `GET_SESSIONS_BY_EVENT_QUERY` to include `isRsvped`, `rsvpCount`, `availableSpots`, `isFull`

**Step 6: Session List UI (Attendee View)**
- On each session card in the attendee event view:
  - Show "RSVP" button if session has `max_participants` set and user hasn't RSVPed
  - Show "Registered" badge if user has RSVPed
  - Show "X / Y spots" or "Session Full" indicator
  - Show "Cancel RSVP" option if already RSVPed
  - Show "Join Waitlist" if session is full and waitlist is enabled

**Step 7: My Schedule View (Attendee)**
- Personal schedule page/tab showing all sessions the attendee has RSVPed for
- Sorted by date/time
- Quick cancel option on each

**Step 8: Dashboard View (Organizer)**
- Show RSVP count on session list in organizer dashboard
- Optionally: export RSVP list per session

### Integration Points
- Waitlist system: When a session is full, integrate with existing `join_waitlist` mutation
- Session reminders: Send reminders only for RSVPed sessions (not all sessions)
- Capacity tracking: RSVP count should sync with `session_capacity.current_attendance`

---

## 6. Huddle Capacity
**Status:** DONE | **Severity:** N/A

Correctly implemented with **optimistic locking** and retry mechanism in `real-time-service/src/networking/huddles/huddles.service.ts`. Returns `huddleFull: true` when capacity exceeded. No action needed.

---

## 7. Event-Level Attendee Cap
**Status:** DONE | **Severity:** N/A

Implemented in commit `1fc4c71`. `max_attendees` column on events table, enforced in both REST and GraphQL registration endpoints. Frontend shows capacity indicator and disables registration when sold out. Error handling in registration modal.

---

## 8. Breakout Room Capacity
**Status:** DONE | **Severity:** N/A

Pre-existing implementation. No action needed.

---

## 9. Waitlist System
**Status:** DONE | **Severity:** N/A

Pre-existing implementation for sessions. No action needed.
