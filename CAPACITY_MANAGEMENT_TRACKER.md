# Capacity Management Tracker

Reference file for tracking capacity-related gaps across the platform.
Items are ordered by severity.

---

## Status Legend
- DONE — Fully implemented and enforced
- PARTIAL — Model/schema exists but enforcement is incomplete
- MISSING — Feature does not exist at all

---

## 1. Ticket Quantity Decrement on Purchase
**Status:** PARTIAL | **Severity:** CRITICAL

**Problem:** `TicketType` model has `quantity_total`, `quantity_sold`, `quantity_reserved`, and computed `quantity_available` / `is_sold_out` properties — but **no code decrements inventory on order completion**. No quantity validation in the order creation flow either. Race condition allows overbooking.

**Files:**
- `event-lifecycle-service/app/models/ticket_type.py` — model with quantity fields
- `event-lifecycle-service/app/services/ticket_management/ticket_service.py` — service layer
- `event-lifecycle-service/app/crud/crud_order.py` — order CRUD (no quantity check)

**What Needs to Happen:**
- [ ] Validate available quantity before creating an order
- [ ] Reserve quantity on order creation (`quantity_reserved += N`)
- [ ] Move reserved to sold on payment confirmation (`quantity_sold += N`, `quantity_reserved -= N`)
- [ ] Release reservation on order cancellation/expiry (`quantity_reserved -= N`)
- [ ] Add row-level locking or optimistic lock to prevent race conditions

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

## 3. Session Join Enforcement
**Status:** PARTIAL | **Severity:** HIGH

**Problem:** `SessionCapacity` model exists with `maximum_capacity`, `current_attendance`, `increment_attendance()`, `decrement_attendance()`, and CHECK constraints. Waitlist system routes to waitlist when full. But there is **no direct session join endpoint** — `max_participants` on the Session model is never enforced. The capacity table is effectively orphaned.

**Files:**
- `event-lifecycle-service/app/models/session_capacity.py` — capacity model
- `event-lifecycle-service/app/crud/crud_session_capacity.py` — CRUD with increment/decrement
- `event-lifecycle-service/app/graphql/waitlist_mutations.py` — waitlist mutations (uses increment)
- `event-lifecycle-service/app/api/v1/endpoints/waitlist.py` — REST waitlist

**What Needs to Happen:**
- [ ] Create session join/RSVP endpoint (or wire up existing session RSVP to use capacity)
- [ ] Enforce `maximum_capacity` check at join time
- [ ] Add transaction isolation to `increment_attendance()` to prevent race conditions

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

## 5. Huddle Capacity
**Status:** DONE | **Severity:** N/A

Correctly implemented with **optimistic locking** and retry mechanism in `real-time-service/src/networking/huddles/huddles.service.ts`. Returns `huddleFull: true` when capacity exceeded. No action needed.

---

## 6. Event-Level Attendee Cap
**Status:** DONE | **Severity:** N/A

Implemented in commit `1fc4c71`. `max_attendees` column on events table, enforced in both REST and GraphQL registration endpoints. Frontend shows capacity indicator and disables registration when sold out. Error handling in registration modal.

---

## 7. Breakout Room Capacity
**Status:** DONE | **Severity:** N/A

Pre-existing implementation. No action needed.

---

## 8. Waitlist System
**Status:** DONE | **Severity:** N/A

Pre-existing implementation for sessions. No action needed.
