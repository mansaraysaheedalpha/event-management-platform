# Venue Sourcing RFP — Frontend Implementation Tasks

**App:** `globalconnect` (Next.js 15 / React 19 / Apollo Client / Tailwind / shadcn)
**Reference:** [API_CONTRACT_RFP.md](API_CONTRACT_RFP.md) — build exactly to this contract
**Reference:** [../VENUE_SOURCING_RFP_SPEC.md](../VENUE_SOURCING_RFP_SPEC.md) — feature spec + HTML mockup
**Depends on:** Golden Directory frontend must be built (venue directory, venue cards, amenity components)

---

## Task R-F1: GraphQL Operations & Types

**Files to create:**

- `src/graphql/rfp.graphql.ts` — NEW (organizer RFP operations)
- `src/graphql/venue-rfp.graphql.ts` — NEW (venue owner RFP operations)

**What to do:**

1. Create organizer operations in `rfp.graphql.ts`:

   **Queries:**
   - `GET_ORGANIZATION_RFPS` — paginated list with status filter
   - `GET_RFP_DETAIL` — full RFP with venues and statuses
   - `GET_RFP_COMPARISON` — comparison dashboard data with exchange rates
   - `GET_RFP_PRE_SEND_SUMMARY` — fit indicators for all selected venues
   - `GET_EXCHANGE_RATES` — currency rates

   **Mutations:**
   - `CREATE_RFP` — create draft
   - `UPDATE_RFP` — update draft
   - `DELETE_RFP` — delete draft
   - `ADD_VENUES_TO_RFP` — add venue selections
   - `REMOVE_VENUE_FROM_RFP` — remove venue
   - `SEND_RFP` — dispatch to venues
   - `EXTEND_RFP_DEADLINE` — extend deadline
   - `CLOSE_RFP` — close without award
   - `DUPLICATE_RFP` — clone to new draft
   - `SHORTLIST_VENUE` — mark as finalist
   - `AWARD_VENUE` — accept proposal
   - `DECLINE_VENUE` — reject proposal

2. Create venue owner operations in `venue-rfp.graphql.ts`:

   **Queries:**
   - `GET_VENUE_RFP_INBOX` — paginated inbox list
   - `GET_VENUE_RFP_DETAIL` — RFP detail with venue's spaces

   **Mutations:**
   - `SUBMIT_VENUE_RESPONSE` — structured response form submission

3. Follow existing `.graphql.ts` pattern for type definitions and gql template literals

**Acceptance criteria:**
- [ ] All operations match API contract GraphQL schema exactly
- [ ] Field selections optimized (don't over-fetch)
- [ ] Fragments used for shared venue/response fields across queries

---

## Task R-F2: RFP List Page (Organizer)

**Route:** `/platform/rfps`

**Files to create:**

- `src/app/(platform)/rfps/page.tsx` — NEW
- `src/app/(platform)/rfps/_components/rfp-list.tsx` — NEW
- `src/app/(platform)/rfps/_components/rfp-card.tsx` — NEW
- `src/app/(platform)/rfps/_components/rfp-stats.tsx` — NEW

**What to do:**

1. **RFP Stats Bar** — summary cards at top:
   - Total RFPs, Active, Awaiting Responses, Awarded
   - Count active RFPs and show "X/5 active" to indicate rate limit

2. **Filter Bar:**
   - Status filter dropdown: All, Draft, Sent, Collecting Responses, Review, Awarded, Closed, Expired
   - Sort: Newest first (default), Deadline soonest

3. **RFP Cards** — each card shows:
   - Title, event type badge
   - Status badge (color-coded: draft=gray, sent=blue, collecting=yellow, review=orange, awarded=green, closed/expired=red)
   - Attendance range
   - Date range or "Flexible dates"
   - Deadline with countdown ("3 days remaining" or "Expired")
   - Venue count + response count (e.g., "3/5 venues responded")
   - Progress bar showing response rate
   - Created date
   - Click → navigate to `/platform/rfps/[id]`

4. **Empty State** — "No RFPs yet. Create your first one to start requesting quotes from venues."

5. **Create RFP Button** — top right, links to `/platform/rfps/new`. Disabled with tooltip if 5 active RFPs reached.

6. **Pagination** — bottom of list

**Acceptance criteria:**
- [ ] List loads with proper loading skeleton
- [ ] Status filter works
- [ ] Rate limit indicator shows active count
- [ ] Cards show correct data and link to detail page
- [ ] Empty state renders correctly

---

## Task R-F3: Create/Edit RFP Page (Organizer)

**Route:** `/platform/rfps/new` and `/platform/rfps/[id]/edit`

**Files to create:**

- `src/app/(platform)/rfps/new/page.tsx` — NEW
- `src/app/(platform)/rfps/[id]/edit/page.tsx` — NEW (reuses same form component)
- `src/app/(platform)/rfps/_components/rfp-form.tsx` — NEW
- `src/app/(platform)/rfps/_components/venue-selector.tsx` — NEW
- `src/app/(platform)/rfps/_components/pre-send-summary.tsx` — NEW

**What to do:**

1. **RFP Form** — two-step flow:

   **Step 1: Event Details** — form fields:
   - Title (text input, required)
   - Event Type (select dropdown, required)
   - Expected Attendance (two number inputs: min + max, required)
   - Preferred Dates (date range picker + "Flexible dates" toggle)
   - Duration (text input)
   - Space Requirements (checkbox group: Theater, Classroom, Banquet, U-shape, Boardroom, Cocktail)
   - Required Amenities (reuse amenity category/checkbox component from Golden Directory)
   - Catering Needs (radio group)
   - Budget Range (two number inputs: min + max, optional, with currency select)
   - Preferred Currency (select — USD, KES, NGN, SLE, ZAR, GHS, GBP, EUR)
   - Additional Notes (textarea)
   - Response Deadline (date picker, default: 7 days from now)
   - Link to Event (optional select from org's events)

   **Step 2: Select Venues** — venue selector:
   - Mini directory browser (reuse `venueDirectory` query)
   - Search by name, filter by country/city
   - Each venue shows: name, city, cover photo thumbnail, capacity, verified badge
   - "Add" button per venue → adds to selected list (max 10)
   - Selected venues shown in right sidebar with "Remove" buttons
   - Counter: "X/10 venues selected"

2. **Pre-Send Summary** — shown after Step 2, before sending:
   - Table of selected venues with fit indicators
   - Capacity fit: colored dot (green/yellow/red) + label
   - Amenity match: percentage with colored bar
   - Price indicator: within/below/above budget
   - "Remove" action per venue if poor fit
   - "Send RFP" button (primary, large)
   - "Save as Draft" button (secondary)

3. **Edit mode** — loads existing draft RFP data into the form. Same component, different data source.

4. **URL parameter support** — if navigated from venue detail page with `?venueId=ven_xxx`, pre-select that venue in Step 2.

**Acceptance criteria:**
- [ ] Form validates all required fields before proceeding to Step 2
- [ ] Venue selector enforces max 10
- [ ] Pre-send summary shows correct fit indicators
- [ ] `?venueId=` query param pre-selects venue
- [ ] Save as draft and send both work correctly
- [ ] Edit mode loads existing data

---

## Task R-F4: RFP Detail Page (Organizer)

**Route:** `/platform/rfps/[id]`

**Files to create:**

- `src/app/(platform)/rfps/[id]/page.tsx` — NEW
- `src/app/(platform)/rfps/[id]/_components/rfp-header.tsx` — NEW
- `src/app/(platform)/rfps/[id]/_components/rfp-timeline.tsx` — NEW
- `src/app/(platform)/rfps/[id]/_components/rfp-venue-list.tsx` — NEW
- `src/app/(platform)/rfps/[id]/_components/rfp-actions.tsx` — NEW

**What to do:**

1. **RFP Header:**
   - Title, status badge, event type badge
   - Key details: attendance, dates, duration, budget, deadline
   - Action buttons based on status:
     - `draft`: Edit, Delete, Send
     - `sent` / `collecting_responses`: Extend Deadline, Close, View Comparison
     - `review`: View Comparison, Close
     - `awarded`: View Comparison (read-only)
     - `closed` / `expired`: Duplicate

2. **RFP Timeline** — vertical timeline showing key events:
   - Created, Sent, First response, Deadline passed, Awarded/Closed
   - Each with timestamp

3. **Venue List** — table/cards of targeted venues:
   - Venue name + cover photo + city
   - Per-venue status badge: received (gray), viewed (blue), responded (green), shortlisted (gold), awarded (green check), declined (red), no_response (gray strike)
   - Capacity fit + amenity match from pre-send data
   - Response time (if responded)
   - Click responded venue → view response detail or go to comparison
   - "View Comparison" link if any responses exist

4. **Response Count Banner:**
   - "3 of 5 venues have responded" with progress bar
   - Deadline countdown: "Deadline in 2 days" or "Deadline passed"

5. **UX Note:** All dashboard features work in `sent` state — do NOT gate behind `collecting_responses`. The organizer can see which venues have `received`/`viewed`, extend deadline, and close from any non-terminal state.

**Acceptance criteria:**
- [ ] All status-dependent actions render correctly
- [ ] Timeline shows accurate timestamps
- [ ] Venue statuses update correctly
- [ ] All actions functional in `sent` state (not gated behind `collecting_responses`)
- [ ] Duplicate creates new draft and navigates to edit page

---

## Task R-F5: Comparison Dashboard (Organizer)

**Route:** `/platform/rfps/[id]/compare`

**Files to create:**

- `src/app/(platform)/rfps/[id]/compare/page.tsx` — NEW
- `src/app/(platform)/rfps/[id]/compare/_components/comparison-table.tsx` — NEW
- `src/app/(platform)/rfps/[id]/compare/_components/comparison-badges.tsx` — NEW
- `src/app/(platform)/rfps/[id]/compare/_components/venue-response-detail.tsx` — NEW
- `src/app/(platform)/rfps/[id]/compare/_components/currency-display.tsx` — NEW

**What to do:**

1. **Comparison Table** — the killer feature. Responsive table with columns:
   - Venue Name (with verified badge, link to directory profile)
   - Availability (Confirmed ✓ / Tentative ~ / Unavailable ✗ — color coded)
   - Space Offered (room name + capacity)
   - Total Cost (original currency)
   - Total Cost (converted to preferred currency)
   - Amenity Match %
   - Response Time (hours/days)
   - Quote Valid Until
   - Actions (Shortlist / Award / Decline)

2. **Badges:**
   - "Best Value" badge on lowest-cost venue (in preferred currency)
   - "Best Match" badge on highest amenity match %
   - Show badges as small colored tags on the venue row

3. **Table Features:**
   - Sort by any column (click column header)
   - Filter toggle: "Hide unavailable venues"
   - Responsive: on mobile, switch to card-based layout

4. **Currency Display** (`CurrencyDisplay` component):
   - Show original amount + currency
   - Below it (smaller): converted amount in preferred currency
   - Tooltip: "Converted at 1 USD = 128.5 KES on Feb 16, 2026"
   - Use exchange rates from query response

5. **Venue Response Detail** — expandable row or modal:
   - Full response details: all pricing breakdown, amenity lists, cancellation policy, deposit, payment schedule, alternative dates, notes
   - Included vs extra-cost amenities side by side

6. **Action Buttons per venue:**
   - Shortlist (star icon) — golden star when shortlisted
   - Award (check icon) — confirmation dialog: "Award this RFP to {venue}? All other venues will be automatically declined."
   - Decline (x icon) — dialog with optional reason textarea
   - Disabled if venue status is already terminal

7. **Top Bar:**
   - "X venues responded" count
   - Exchange rate info: "Rates as of Feb 16, 2026"
   - Back to RFP detail link

**Acceptance criteria:**
- [ ] Table renders all responded venues with correct data
- [ ] Sort by all columns works
- [ ] Currency conversion displays correctly with tooltip
- [ ] Badges correctly computed and displayed
- [ ] Award triggers confirmation dialog and auto-declines others
- [ ] Responsive layout (table → cards on mobile)
- [ ] Filter hides unavailable venues

---

## Task R-F6: Venue RFP Inbox

**Route:** `/platform/venues/[venueId]/rfps`

**Files to create:**

- `src/app/(platform)/venues/[venueId]/rfps/page.tsx` — NEW
- `src/app/(platform)/venues/[venueId]/rfps/_components/rfp-inbox-list.tsx` — NEW
- `src/app/(platform)/venues/[venueId]/rfps/_components/rfp-inbox-item.tsx` — NEW

**What to do:**

1. **Inbox Header:**
   - Title: "RFP Inbox — {Venue Name}"
   - Unread count badge (RFPs in `received` status)

2. **Filter Bar:**
   - Status filter: All, New, Viewed, Responded, Shortlisted, Awarded, Declined

3. **Inbox Items** — list style (like email inbox):
   - Title + event type badge
   - Organizer name
   - Attendance range + dates
   - Deadline with countdown ("Respond by Feb 23 — 3 days remaining")
   - Status indicator: new (blue dot), viewed (no dot), responded (green check), etc.
   - Click → navigate to `/platform/venues/[venueId]/rfps/[rfpId]`

4. **Empty State:** "No venue requests yet. When organizers send you an RFP, it will appear here."

5. **Navigation:** Link from venue owner dashboard sidebar (add "RFP Inbox" with badge count)

**Acceptance criteria:**
- [ ] Inbox loads with proper loading state
- [ ] Items sorted by received date (newest first)
- [ ] Status filter works
- [ ] Deadline countdown displays correctly
- [ ] Unread indicator for `received` status items
- [ ] Link added to venue dashboard navigation

---

## Task R-F7: Venue RFP Response Form

**Route:** `/platform/venues/[venueId]/rfps/[rfpId]`

**Files to create:**

- `src/app/(platform)/venues/[venueId]/rfps/[rfpId]/page.tsx` — NEW
- `src/app/(platform)/venues/[venueId]/rfps/[rfpId]/_components/rfp-detail-view.tsx` — NEW
- `src/app/(platform)/venues/[venueId]/rfps/[rfpId]/_components/response-form.tsx` — NEW
- `src/app/(platform)/venues/[venueId]/rfps/[rfpId]/_components/response-submitted.tsx` — NEW

**What to do:**

1. **RFP Detail View** — read-only display of the RFP requirements:
   - Event details card: title, type, attendance, dates, duration
   - Space requirements: layout types needed (badges)
   - Required amenities: grouped by category
   - Catering needs
   - Additional notes
   - Deadline countdown bar: "You have 3 days to respond"

2. **Response Form** — structured form (shown if status is `received` or `viewed`):

   **Availability Section:**
   - Radio: Confirmed / Tentative / Unavailable
   - If "Unavailable" selected → show simplified form (just alternative dates + notes)

   **Space Selection:**
   - Dropdown of venue's own spaces (from `venueSpaces` in query)
   - Show capacity + layout options for selected space

   **Pricing Section:**
   - Currency selector (defaults to venue's common currency)
   - Space Rental Price (number input)
   - Catering Price Per Head (number input, conditional on RFP catering needs)
   - AV/Equipment Fees (number input)
   - Setup/Cleanup Fees (number input)
   - Other Fees (number input + description text)
   - **Live total calculator** — auto-sums all fees + (catering × max attendance)

   **Amenities Section:**
   - Show organizer's required amenities as checklist
   - For each amenity: "Included" checkbox or "Extra cost" checkbox + price input
   - Pre-check amenities that match venue's directory profile

   **Terms Section:**
   - Cancellation Policy (textarea with suggested format)
   - Deposit Amount (number input)
   - Payment Schedule (textarea)
   - Quote Valid Until (date picker, default: 30 days from now)

   **Additional:**
   - Alternative Dates (date picker, shown if organizer dates don't work)
   - Notes (textarea)

   **Submit Button:** "Submit Proposal" — confirmation dialog before sending

3. **Response Submitted View** — shown if venue has already responded:
   - Read-only display of submitted response
   - Status indicator (responded / shortlisted / awarded / declined)
   - If awarded: celebration banner
   - If declined: decline reason shown

4. **Deadline Passed View** — shown if deadline has passed and venue didn't respond:
   - "This RFP has expired. You did not submit a response in time."

**Acceptance criteria:**
- [ ] Form correctly conditional on availability selection
- [ ] Live total calculator updates in real-time
- [ ] Amenity checkboxes pre-checked from venue profile
- [ ] Submission triggers confirmation dialog
- [ ] Already-responded shows read-only view
- [ ] Deadline-passed shows expired message
- [ ] Currency selection works

---

## Task R-F8: Integration Points & Shared Components

**Files to create/modify:**

- `src/components/rfp/rfp-status-badge.tsx` — NEW
- `src/components/rfp/venue-status-badge.tsx` — NEW
- `src/components/rfp/deadline-countdown.tsx` — NEW
- `src/components/rfp/capacity-fit-indicator.tsx` — NEW
- `src/components/rfp/amenity-match-bar.tsx` — NEW
- `src/components/rfp/currency-display.tsx` — NEW

**Modify existing pages:**

- `src/app/(public)/venues/[slug]/page.tsx` — ADD "Request a Quote" button
- `src/app/(public)/venues/page.tsx` — ADD "Add to RFP" button on venue cards
- `src/app/(platform)/venues/page.tsx` — ADD "RFP Inbox" link in venue dashboard nav

**What to do:**

1. **Shared Components:**

   - `RFPStatusBadge` — color-coded status badge for RFP-level states (draft=gray, sent=blue, collecting=amber, review=orange, awarded=green, closed=slate, expired=red)
   - `VenueStatusBadge` — color-coded for per-venue states (received=gray, viewed=blue, responded=emerald, shortlisted=amber, awarded=green, declined=red, no_response=slate)
   - `DeadlineCountdown` — shows "3 days remaining" or "5 hours remaining" or "Expired". Red text when < 24h.
   - `CapacityFitIndicator` — colored dot + label (green=Good fit, yellow=Tight fit/Oversized, red=Poor fit)
   - `AmenityMatchBar` — percentage bar with color (green >= 80%, yellow 50-79%, red < 50%)
   - `CurrencyDisplay` — dual-line display: original amount + converted amount with tooltip

2. **Venue Detail Page Integration** (`/venues/[slug]`):
   - Add "Request a Quote" button in the contact sidebar
   - On click: if logged in → navigate to `/platform/rfps/new?venueId={venueId}`. If not logged in → prompt login.
   - Button only shows for logged-in organizers (not venue owners viewing their own venue)

3. **Venue Directory Integration** (`/venues`):
   - Add small "Request Quote" button on each venue card
   - Same behavior as venue detail page button

4. **Venue Dashboard Nav** (`/platform/venues`):
   - Add "RFP Inbox" link in the venue owner sidebar/navigation
   - Show badge with unread count (RFPs in `received` status)

**Acceptance criteria:**
- [ ] All shared components render correctly with all state variants
- [ ] "Request a Quote" button works on venue detail page
- [ ] Button navigates with `?venueId=` param
- [ ] Login prompt shown for unauthenticated users
- [ ] RFP Inbox link added to venue dashboard navigation with badge

---

## Execution Order

```
R-F1 (GraphQL Operations)
  ↓
R-F8 (Shared Components)
  ↓
R-F2 (RFP List)      R-F6 (Venue Inbox)
  ↓                     ↓
R-F3 (Create/Edit)    R-F7 (Response Form)
  ↓                     ↓
R-F4 (RFP Detail)      └───────────────────┐
  ↓                                         ↓
R-F5 (Comparison Dashboard) ←─ Integration Points from R-F8
```

R-F1 must be first. R-F8 should be early since many components depend on it.
R-F2+R-F3+R-F4+R-F5 (organizer flow) and R-F6+R-F7 (venue flow) can be built in parallel.
