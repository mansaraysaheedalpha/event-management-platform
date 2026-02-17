# Venue Sourcing — Waitlist & Queue System: Frontend Tasks

**Reference:** Read these before starting:
1. `VENUE_SOURCING_WAITLIST_SPEC.md` (root) — the approved feature specification
2. `venue-sourcing-docs/API_CONTRACT_WAITLIST.md` — the API contract (source of truth for types, endpoints, responses)
3. `venue-sourcing-docs/API_CONTRACT_RFP.md` — the RFP API contract (for integration points)

**Codebase:** `globalconnect/` (Next.js 15, React 19, Apollo Client, Tailwind CSS, shadcn/ui)

**Existing patterns to follow:**
- RFP pages: `app/(platform)/platform/rfps/` — follow the same layout, components, loading states
- GraphQL operations: `lib/graphql/` — follow existing query/mutation file structure
- Components: `components/` — use existing shadcn/ui components (Button, Card, Badge, Dialog, Table, etc.)
- Venue directory pages: `app/(public)/venues/` — for integration points

---

## Task Dependency Graph

```
W-F1 (GraphQL Operations & Types)
  ├── W-F2 (Waitlist Dashboard Page)
  ├── W-F3 (Waitlist Entry Detail Page)
  ├── W-F4 (Join Waitlist — Comparison Dashboard Integration)
  ├── W-F5 (Venue Availability Badge Component)
  │     └── W-F6 (Directory & Venue Detail Integration)
  └── W-F7 (Venue Owner Availability Management)
W-F8 (Hold Timer & Real-Time Updates) ← depends on W-F2, W-F3
```

---

## W-F1: GraphQL Operations & Types

**Create GraphQL operations for all waitlist queries and mutations.**

### Types File

**Create `lib/graphql/waitlist-types.ts`** (or add to existing types file)

```typescript
// Enums
type WaitlistStatus = 'WAITING' | 'OFFERED' | 'CONVERTED' | 'EXPIRED' | 'CANCELLED'
type CancellationReason = 'NO_LONGER_NEEDED' | 'FOUND_ALTERNATIVE' | 'DECLINED_OFFER' | 'OTHER'
type AvailabilityStatus = 'ACCEPTING_EVENTS' | 'LIMITED_AVAILABILITY' | 'FULLY_BOOKED' | 'SEASONAL' | 'NOT_SET'

// Types matching API Contract Section 3.2
type VenueWaitlistEntry = { ... }
type WaitlistEntryListResult = { ... }
type WaitlistConversionResult = { ... }
type VenueAvailability = { ... }
type AvailabilitySignalSummary = { ... }
type AvailabilityBadge = { ... }
```

### Queries

**Create `lib/graphql/waitlist-queries.ts`**

| Query | Used By |
|---|---|
| `MY_WAITLIST_ENTRIES` | Waitlist dashboard (W-F2) |
| `WAITLIST_ENTRY` | Waitlist entry detail (W-F3) |
| `VENUE_AVAILABILITY` | Venue owner availability management (W-F7) |
| `VENUE_AVAILABILITY_BADGE` | Availability badge component (W-F5) |

### Mutations

**Create `lib/graphql/waitlist-mutations.ts`**

| Mutation | Used By |
|---|---|
| `JOIN_VENUE_WAITLIST` | Comparison dashboard join button (W-F4) |
| `CONVERT_WAITLIST_HOLD` | Waitlist entry detail — convert action (W-F3) |
| `CANCEL_WAITLIST_ENTRY` | Waitlist entry detail — cancel action (W-F3) |
| `RESPOND_STILL_INTERESTED` | Email deep link handler (W-F3) |
| `SET_VENUE_AVAILABILITY` | Venue owner availability toggle (W-F7) |
| `CLEAR_VENUE_AVAILABILITY_OVERRIDE` | Venue owner availability management (W-F7) |
| `RESOLVE_WAITLIST_CIRCUIT_BREAKER` | Venue owner circuit breaker resolution (W-F7) |

---

## W-F2: Waitlist Dashboard Page

**Create `app/(platform)/platform/waitlists/page.tsx`**

This is the organizer's central waitlist management page.

### Layout

- **Header:** "My Waitlists" title + active entry count badge (e.g., "3 of 5 active")
- **Filter tabs:** All | Active (waiting + offered) | Past (converted + expired + cancelled)
- **Entry cards** (not a table — cards work better for the data density):

Each card shows:

| Element | Description |
|---|---|
| Venue name + cover photo thumbnail | Link to venue detail page |
| Availability badge | Green/yellow/red/blue/gray dot + label (use W-F5 component) |
| Queue position | Bold "#3 in line" — only shown for `waiting` status |
| Status badge | Colored badge: waiting (blue), offered (orange pulse), converted (green), expired (gray), cancelled (gray) |
| Hold timer | Countdown "23h 14m remaining" — only shown for `offered` status (use W-F8) |
| Source RFP | Link to the original RFP: "From: Annual Tech Conference 2026 Venue" |
| Desired dates | "Jun 15-17, 2026" or "Flexible dates" |
| Attendance | "200-300 guests" |
| Joined date | "Joined Feb 17, 2026" |
| Actions | "Cancel" button (if waiting), "Claim Hold" / "Pass" buttons (if offered) |

### States

- **Loading:** Skeleton cards
- **Empty (no entries):** Friendly empty state: "No waitlist entries yet. When you send an RFP and a venue is unavailable, you can join their waitlist from the comparison dashboard."
- **Empty (filtered):** "No [status] entries"

### Actions

- **Cancel (waiting):** Confirmation dialog → `CANCEL_WAITLIST_ENTRY` mutation with reason selector (dropdown: no_longer_needed, found_alternative, other)
- **Claim Hold (offered):** Confirmation dialog explaining "This will create a new RFP to [Venue Name]" → `CONVERT_WAITLIST_HOLD` mutation → redirect to the new RFP draft page
- **Pass (offered):** Confirmation dialog → `CANCEL_WAITLIST_ENTRY` mutation with reason = `declined_offer`

### Pagination

Use existing pagination pattern. Default page_size: 10.

---

## W-F3: Waitlist Entry Detail Page

**Create `app/(platform)/platform/waitlists/[id]/page.tsx`**

A focused view of a single waitlist entry with full context.

### Sections

1. **Status Header:**
   - Large status indicator with appropriate styling
   - If `offered`: prominent hold timer countdown (W-F8) + "Claim Hold" / "Pass" buttons
   - If `waiting`: queue position display + "Cancel" button
   - If terminal: status label + timestamp

2. **Venue Card:**
   - Venue name, photo, city, country, availability badge
   - Link to venue detail page

3. **Original RFP Context:**
   - Event type, dates, attendance, space requirements
   - Link to source RFP detail page

4. **Timeline:**
   - Joined at
   - Hold offered at (if applicable)
   - Hold expires at (if applicable)
   - Converted/cancelled/expired at (if terminal)
   - Expiry date (when entry will auto-expire)

### "Still Interested?" Handler

If the user arrives via the "still interested?" email deep link (e.g., `/platform/waitlists/[id]?action=still_interested`):
- Show a confirmation dialog: "Are you still interested in [Venue Name] for your event?"
- "Yes, keep me on the waitlist" → `RESPOND_STILL_INTERESTED(interested: true)`
- "No, remove me" → `RESPOND_STILL_INTERESTED(interested: false)` → entry cancelled

---

## W-F4: Join Waitlist — Comparison Dashboard Integration

**Modify the existing RFP Comparison Dashboard page.**

### Where: Comparison Dashboard (`app/(platform)/platform/rfps/[id]/compare/page.tsx`)

### What to add:

For each venue in the comparison table/cards that has `response.availability === 'UNAVAILABLE'`:

1. **"Join Waitlist" button** — appears next to or below the unavailable status badge
2. Button states:
   - **Default:** "Join Waitlist" (outline button, blue)
   - **Loading:** Spinner + "Joining..."
   - **Already on waitlist:** "On Waitlist (#3)" (disabled, shows position) — check if user already has an active entry for this venue
   - **Rate limited:** "Waitlist Full (5/5)" — disabled, tooltip explains the limit

3. **On click:** `JOIN_VENUE_WAITLIST(sourceRfpVenueId)` mutation
4. **On success:** Show toast "Added to waitlist for [Venue Name]. You're #X in line." + update button to "On Waitlist (#X)"
5. **On error (409 - duplicate):** Toast "You're already on the waitlist for this venue"
6. **On error (429 - rate limit):** Toast "You've reached the maximum of 5 active waitlist entries"

### Also add to: RFP Detail Page

On the RFP detail page (`app/(platform)/platform/rfps/[id]/page.tsx`), in the venue list section:
- For venues with `status: 'responded'` and `response.availability: 'unavailable'`, show a small "Join Waitlist" link

---

## W-F5: Venue Availability Badge Component

**Create `components/venue/availability-badge.tsx`**

A reusable badge component that displays the venue's availability status.

### Props

```typescript
interface AvailabilityBadgeProps {
  status: AvailabilityStatus
  size?: 'sm' | 'md' | 'lg'    // sm for directory cards, md for detail pages, lg for dashboard
  showLabel?: boolean            // false for compact mode (just the dot)
}
```

### Rendering

| Status | Color | Dot | Label |
|---|---|---|---|
| `ACCEPTING_EVENTS` | green-500 | Filled green circle | "Accepting Events" |
| `LIMITED_AVAILABILITY` | yellow-500 | Filled yellow circle | "Limited Availability" |
| `FULLY_BOOKED` | red-500 | Filled red circle | "Fully Booked" |
| `SEASONAL` | blue-500 | Filled blue circle | "Seasonal Venue" |
| `NOT_SET` | gray-400 | Outlined gray circle | "Status Unknown" |

Use Tailwind utility classes. Match the existing badge patterns in the codebase (likely using shadcn Badge component or custom).

### Data Fetching

The badge reads `availabilityStatus` from the venue object (extended VenueType in GraphQL). It does NOT make its own query — the parent component provides the data.

---

## W-F6: Directory & Venue Detail Integration

**Modify existing venue pages to show the availability badge.**

### 1. Golden Directory Listing (`app/(public)/venues/page.tsx`)

On each venue card:
- Add the `<AvailabilityBadge status={venue.availabilityStatus} size="sm" />` component
- Position: below the venue name or in the card footer area
- Ensure the venue list GraphQL query includes `availabilityStatus` field

### 2. Venue Detail Page (`app/(public)/venues/[slug]/page.tsx`)

In the venue header area:
- Add `<AvailabilityBadge status={venue.availabilityStatus} size="md" />` next to the venue name/verified badge
- Ensure the venue detail GraphQL query includes `availabilityStatus`, `availabilityBadgeColor`, `availabilityBadgeLabel`

### 3. RFP Pre-Send Summary

In the pre-send summary view (shown before sending an RFP):
- Add availability badge next to each venue's capacity fit and amenity match indicators
- This helps organizers see venue availability before sending

---

## W-F7: Venue Owner Availability Management

**Create availability management in the venue owner dashboard.**

### Where: Venue Dashboard (`app/(platform)/platform/venues/[venueId]/page.tsx` or similar)

### What to add:

An "Availability Status" card/section with:

1. **Current status display:**
   - Large availability badge
   - If manual override active: "Manually set on [date]" label
   - If inference-driven: "Auto-detected from your RFP responses" label

2. **Status selector:**
   - Radio group or dropdown with 4 options: Accepting Events, Limited Availability, Fully Booked, Seasonal
   - "Update Status" button → `SET_VENUE_AVAILABILITY` mutation

3. **Override indicator:**
   - If manual override is active, show: "You've manually set your availability. The system won't auto-update it."
   - "Return to auto-detection" link → `CLEAR_VENUE_AVAILABILITY_OVERRIDE` mutation

4. **Signal summary** (informational, read-only):
   - "Based on your recent RFP responses: X confirmed, Y tentative, Z unavailable"
   - Shows the system's inferred status alongside the displayed status
   - Only visible to venue owner (not public)

5. **Circuit breaker alert** (conditional):
   - If the venue has an active circuit breaker pause (3 consecutive no-responses on waitlist), show an alert banner:
   - "Your waitlist has been paused — 3 organizers in a row didn't respond to their hold offers. Would you like to keep the waitlist active?"
   - "Resume Waitlist" button → `RESOLVE_WAITLIST_CIRCUIT_BREAKER` mutation → cascade resumes
   - "Dismiss" → no action (the `process_circuit_breaker_expiry` background job will deactivate after 7 days)
   - This alert appears on the venue dashboard and the availability management section

---

## W-F8: Hold Timer & Real-Time Updates

### Hold Timer Component

**Create `components/waitlist/hold-timer.tsx`**

A countdown timer for active holds.

### Props

```typescript
interface HoldTimerProps {
  expiresAt: string          // ISO datetime string
  remainingSeconds: number   // initial value from server
  onExpired?: () => void     // callback when timer hits zero
  size?: 'sm' | 'lg'        // sm for list cards, lg for detail page
}
```

### Behavior

1. Initialize with `remainingSeconds` from the server (avoids clock sync issues)
2. Decrement locally every second using `setInterval`
3. Display format:
   - If > 24h: "1d 23h remaining"
   - If > 1h: "23h 14m remaining"
   - If < 1h: "45m 32s remaining" (orange text)
   - If < 15m: "14m 58s remaining" (red text, pulsing)
   - If expired: "Hold Expired" (red, static)
4. Call `onExpired` when timer reaches zero → refetch entry to get updated status

### Real-Time Position Updates

For the waitlist dashboard and detail pages, set up a **polling interval** (every 30 seconds) to refetch the entry data. This keeps queue positions and statuses current without WebSocket complexity at launch.

Use Apollo Client's `pollInterval` option on the queries:
```typescript
const { data } = useQuery(WAITLIST_ENTRY, {
  variables: { id },
  pollInterval: 30000, // 30 seconds
})
```

> **Future:** Replace polling with Socket.IO events for true real-time updates. The backend will emit `waitlist.position_changed` and `waitlist.hold_expired` events. For launch, polling is sufficient.

---

## Verification Checklist

After implementation, verify:

- [ ] Waitlist dashboard shows all entries with correct status badges and queue positions
- [ ] "Join Waitlist" button appears only for unavailable venues in comparison dashboard
- [ ] Joining waitlist shows queue position in success toast
- [ ] Rate limit (5 active) is communicated clearly when reached
- [ ] Duplicate join attempt shows appropriate error
- [ ] Hold timer counts down accurately and changes color as it approaches expiry
- [ ] "Claim Hold" creates a new draft RFP and redirects to it
- [ ] "Pass" triggers cancel with reason `declined_offer`
- [ ] Cancel dialog includes reason selector
- [ ] Availability badge renders correctly at all sizes on directory cards, venue detail, and dashboard
- [ ] Venue owner can set/clear availability status
- [ ] Override indicator clearly shows whether status is manual or auto-detected
- [ ] "Still interested?" email deep link works and shows confirmation dialog
- [ ] Polling keeps data fresh on dashboard and detail pages
- [ ] All pages have proper loading skeletons and empty states
- [ ] Navigation from waitlist entry → source RFP works
- [ ] Navigation from waitlist entry → venue detail works
