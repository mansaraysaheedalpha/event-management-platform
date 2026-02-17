# Venue Sourcing — Standardized RFP System Specification

**Phase 1, Section 2: Request for Proposal System**
**Date:** February 2026
**Status:** Approved (Feb 2026)
**Depends on:** Golden Directory (Phase 1, Section 1) — venues, spaces, amenities, and pricing must exist first

---

## 1. Overview

The Standardized RFP system allows event organizers to send structured venue requests to multiple venues simultaneously and compare responses side-by-side. Instead of calling venues individually or sending unstructured emails, organizers fill out one form, select target venues from the Golden Directory, and receive structured, comparable responses on a single comparison dashboard.

This is the second building block of the venue sourcing pipeline. The Golden Directory provides the data; the RFP system provides the workflow.

---

## 2. The RFP Lifecycle

### Step 1: Organizer Creates an RFP

The organizer fills out a single standardized form capturing:

| Field | Type | Notes |
|---|---|---|
| Title | Text | e.g., "Annual Tech Conference 2026 Venue" |
| Event Type | Enum | Conference, Wedding, Corporate Retreat, Workshop, Exhibition, Social Event, Other |
| Expected Attendance | Range | Min-max headcount (e.g., 200-300). Venues need flexibility, not exact numbers |
| Preferred Date(s) | Flexible | Single date, date range, OR "flexible within these weeks" |
| Duration | Text | Hours or days (e.g., "2 full days" or "4 hours") |
| Space Requirements | Multi-select | Layout types needed: Theater, Classroom, Banquet, U-shape, Boardroom, Cocktail |
| Required Amenities | Multi-select | Pulled directly from Golden Directory amenity system (structured data) |
| Catering Needs | Enum | None, In-house preferred, External allowed, No preference |
| Budget Range | Range | Optional but strongly encouraged. Min-max in organizer's preferred currency |
| Preferred Currency | Select | The currency for comparison dashboard display (e.g., USD, KES, NGN) |
| Additional Notes | Text | Free text for special requirements (accessibility, branding, AV, etc.) |
| Response Deadline | Date | Default: 7 days from send. Configurable by organizer |
| Linked Event | Optional FK | Can optionally link to an existing event on the platform |

### Step 2: Organizer Selects Target Venues

- Organizer browses the Golden Directory, selects 1-10 venues, and adds them to the RFP
- **Maximum 10 venues per RFP** — prevents spam-blasting, maintains venue trust
- **Maximum 5 active RFPs per organizer** — prevents venue flooding. An "active" RFP is one in `draft`, `sent`, `collecting_responses`, or `review` state. Terminal states (`awarded`, `closed`, `expired`) don't count. This limit can be relaxed later for premium accounts
- Before sending, the system shows a **pre-send summary** with fit indicators per venue:

**Capacity Fit Indicator** (compares venue's `total_capacity` against RFP's `max_attendance`):

| Color | Condition | Label |
|---|---|---|
| Green | Capacity is 100-150% of max attendance | Good fit |
| Yellow | Capacity is 80-99% or 151-200% of max attendance | Tight fit / Oversized |
| Red | Capacity is below 80% or above 200% of max attendance | Poor fit |

**Amenity Match Percentage**: `(matched amenities / required amenities) * 100`. Displayed as a percentage with color coding: green >= 80%, yellow 50-79%, red < 50%. If no amenities are required, show "N/A".

**Price Range Indicator**: If the venue has pricing data in the Golden Directory AND the organizer specified a budget range, show whether the venue's base space rental falls within, below, or above the budget. If either is missing, show "No data".

- This helps organizers remove poor-fit venues before sending

> **Future (Phase 2):** Smart match — platform suggests venues based on RFP criteria. The data model is designed to support this, but manual selection is the launch feature.

### Step 3: Venues Receive and Respond

Venue owners are notified via **three channels simultaneously**:
1. **In-app notification** (notification bell in venue dashboard)
2. **Email** (via Resend, existing infrastructure)
3. **WhatsApp** (via Africa's Talking or WhatsApp Business API — critical for African markets)

The venue sees the RFP details and fills out a **structured response form** (not free text):

| Field | Type | Notes |
|---|---|---|
| Availability | Enum | Confirmed, Tentative, Unavailable |
| Proposed Space(s) | Select | Which of their listed rooms/spaces they're offering |
| Space Rental Price | Decimal + Currency | Per-day or per-event cost for the space |
| Catering Price Per Head | Decimal + Currency | If applicable |
| AV/Equipment Fees | Decimal + Currency | If applicable |
| Setup/Cleanup Fees | Decimal + Currency | If applicable |
| Other Fees | Decimal + Currency + Description | Any additional costs |
| Included Amenities | Checkboxes | Which of the organizer's requested amenities are included at no extra cost |
| Extra-Cost Amenities | Checkboxes + Price | Amenities available but at additional cost |
| Cancellation Policy | Text | Structured: "Full refund before X days, 50% before Y days, no refund after Z days" |
| Deposit Required | Decimal + Currency | Amount needed to secure booking |
| Payment Schedule | Text | e.g., "50% deposit, 50% 7 days before event" |
| Alternative Dates | Date(s) | If requested dates unavailable, venue can suggest alternatives |
| Quote Valid Until | Date | How long this proposal is valid |
| Notes | Text | Free text for anything else |

**Critical:** All pricing in the response is a **snapshot** — stored as denormalized data in the response record, not a live reference to the venue's directory pricing. Prices change; accepted quotes must not shift.

### Step 4: Response Deadline

- Every RFP has a response deadline set by the organizer (default: 7 days)
- A background job (Celery scheduled task) runs at the deadline to:
  - Transition the RFP status from `collecting_responses` to `review`
  - Mark non-responding venues as `no_response`
  - Send a notification to the organizer: "Your RFP deadline has passed. X of Y venues responded."
- The organizer can **extend the deadline** if needed (e.g., add 3 more days)
- Venues **cannot respond after the deadline** unless the organizer extends it

### Step 5: Comparison Dashboard

The organizer's **killer feature**. All responses side-by-side in a structured table:

| Column | Source | Notes |
|---|---|---|
| Venue Name | Directory | With verified badge |
| Availability | Response | Confirmed / Tentative / Unavailable |
| Total Estimated Cost | Calculated | Auto-sum of all pricing fields in response |
| Total in Preferred Currency | Calculated | Converted using daily-cached exchange rates |
| Space Offered | Response | Room name + capacity |
| Amenity Match % | Calculated | How many of the organizer's required amenities this venue has (pre-computable from directory data) |
| Response Time | Calculated | Time between RFP send and venue response |
| Quote Valid Until | Response | Expiry date of the proposal |

**Auto-badges:**
- **Best Value** — lowest total cost (in preferred currency)
- **Best Match** — highest amenity match percentage
- These are simple calculations, not AI

**Dashboard actions:**
- Sort by any column
- Filter out unavailable venues
- Shortlist (mark 2-3 as finalists)

### Step 6: Organizer Decides

From the comparison dashboard, the organizer can:

| Action | What Happens |
|---|---|
| **Accept** | Venue notified, RFP status → Awarded. Only one venue can be accepted per RFP |
| **Decline** | Venue notified with optional reason. Per-venue status → Declined |
| **Shortlist** | Mark as finalist. Per-venue status → Shortlisted. No notification sent yet |
| ~~Negotiate~~ | **Deferred to fast-follow.** Schema is designed for it but no UI at launch |

---

## 3. State Machines

### 3.1 RFP States (Overall)

| State | Description | Transitions To |
|---|---|---|
| `draft` | Organizer is still building the RFP | `sent` |
| `sent` | RFP dispatched to selected venues, awaiting first response | `collecting_responses`, `closed` |
| `collecting_responses` | At least one venue has responded, deadline not yet passed | `review`, `closed` |
| `review` | Deadline passed OR all venues responded, organizer is comparing | `awarded`, `closed` |
| `awarded` | Organizer has accepted a proposal | (terminal) |
| `closed` | RFP closed without awarding (cancelled or went elsewhere) | (terminal) |
| `expired` | Deadline passed with zero responses | (terminal) |

**Automatic transitions:**
- `sent` → `collecting_responses`: when first venue responds
- `collecting_responses` → `review`: when deadline passes (background job)
- `sent` → `expired`: when deadline passes with zero responses (background job)

> **Important UX note:** The `sent` state is **not** a "waiting" state. While in `sent`, the organizer dashboard must be fully functional — the organizer can view RFP details, see which venues have `received` or `viewed` the RFP (via per-venue states), extend the deadline, and close/cancel the RFP. The frontend must not gate any organizer actions behind `collecting_responses`. The only difference between `sent` and `collecting_responses` is whether any venue has submitted a response yet.

### 3.2 Venue Response States (Per Venue Per RFP)

| State | Description | Transitions To |
|---|---|---|
| `received` | Venue has been notified | `viewed`, `no_response` |
| `viewed` | Venue has opened the RFP details | `responded`, `no_response` |
| `responded` | Venue has submitted their proposal | `shortlisted`, `awarded`, `declined` |
| `shortlisted` | Organizer marked them as a finalist | `awarded`, `declined` |
| `awarded` | Organizer accepted their proposal | (terminal) |
| `declined` | Organizer passed on them | (terminal) |
| `no_response` | Deadline passed without response | (terminal) |

---

## 4. Notification Strategy

Notifications are **channel-agnostic** — the system creates a notification event, and delivery adapters handle each channel independently.

### Notification Events

| Event | Recipient | Channels | Priority |
|---|---|---|---|
| New RFP received | Venue owner | In-app + Email + WhatsApp | High |
| RFP deadline reminder (24h before) | Venue owner (if not responded) | Email + WhatsApp | Medium |
| Venue responded | Organizer | In-app + Email | Medium |
| All venues responded | Organizer | In-app + Email | High |
| RFP deadline passed | Organizer | In-app + Email | High |
| Proposal accepted | Venue owner | In-app + Email + WhatsApp | High |
| Proposal declined | Venue owner | In-app + Email | Low |
| Deadline extended | Venue owner (non-responders) | Email + WhatsApp | Medium |

### WhatsApp Integration

- Use Africa's Talking WhatsApp API (already integrated for SMS) or WhatsApp Business API
- Messages are templated (WhatsApp requires pre-approved templates)
- Track delivery status: sent, delivered, read

> **Action item:** Submit these templates for WhatsApp approval early — approval can take 2-5 business days and should not block launch.

**WhatsApp Template Structures** (submit for approval before development):

**Template 1: `rfp_new_request`** (High priority)
```
Hi {{1}},

You've received a new venue request on GlobalConnect!

Event: {{2}}
Type: {{3}}
Date: {{4}}
Guests: {{5}}

Review and respond here: {{6}}

Deadline to respond: {{7}}
```
Variables: `{venue_contact_name}`, `{rfp_title}`, `{event_type}`, `{preferred_dates}`, `{attendance_range}`, `{dashboard_deep_link}`, `{response_deadline}`

**Template 2: `rfp_deadline_reminder`** (Medium priority)
```
Hi {{1}},

Reminder: You have a pending venue request for "{{2}}" that needs your response.

Deadline: {{3}} ({{4}} remaining)

Respond now: {{5}}
```
Variables: `{venue_contact_name}`, `{rfp_title}`, `{deadline_date}`, `{hours_remaining}`, `{dashboard_deep_link}`

**Template 3: `rfp_proposal_accepted`** (High priority)
```
Congratulations {{1}}! 🎉

Your proposal for "{{2}}" has been accepted by the organizer.

Log in to view details and next steps: {{3}}
```
Variables: `{venue_contact_name}`, `{rfp_title}`, `{dashboard_deep_link}`

**Template 4: `rfp_deadline_extended`** (Medium priority)
```
Hi {{1}},

The deadline for venue request "{{2}}" has been extended.

New deadline: {{3}}

You can still submit your proposal: {{4}}
```
Variables: `{venue_contact_name}`, `{rfp_title}`, `{new_deadline}`, `{dashboard_deep_link}`

---

## 5. Currency Conversion

- Organizer sets a **preferred currency** on the RFP (e.g., USD)
- Exchange rates fetched daily from a free API (e.g., exchangerate-api.com) and cached in Redis
- Comparison dashboard shows **both** original currency and converted amount
- Conversion is for **display only** — all stored amounts remain in the venue's original currency
- Rate used for conversion is stored on each display (so the organizer can see "converted at 1 USD = 128.5 KES on Feb 16")

---

## 6. Pages (Frontend)

### 6.1 Organizer Pages

| Route | Description |
|---|---|
| `/platform/rfps` | RFP list — all organizer's RFPs with status badges, response counts |
| `/platform/rfps/new` | Create RFP form — event details + venue selection from directory |
| `/platform/rfps/[id]` | RFP detail — overview, status, timeline, list of targeted venues |
| `/platform/rfps/[id]/compare` | Comparison dashboard — side-by-side venue responses |

### 6.2 Venue Owner Pages

| Route | Description |
|---|---|
| `/platform/venues/[venueId]/rfps` | RFP inbox — list of received RFPs with status |
| `/platform/venues/[venueId]/rfps/[rfpId]` | RFP detail + response form |

> **Known limitation (launch):** If an organization manages multiple venues, the RFP inbox is per-venue — there is no aggregate "all RFPs across all my venues" view. The venue owner must navigate to each venue's inbox individually. This is acceptable at launch since most early venues will be single-property operators. An aggregate inbox can be added as a fast-follow when multi-property chains onboard.

### 6.3 Integration Points

- **Venue Detail Page** (`/venues/[slug]`): The "Request a Quote" button opens the RFP creation flow (`/platform/rfps/new`) with that venue pre-selected in the venue list. It does **not** auto-create and send an RFP — the organizer still fills out the full form and can add more venues before sending. If the organizer is not logged in, prompt login first.
- **Golden Directory** (`/venues`): "Add to RFP" button on each venue card (when organizer has a draft RFP). If no draft RFP exists, the button says "Request a Quote" and behaves like the venue detail page button above.

---

## 7. Negotiation (Schema-Ready, UI Deferred)

The data model includes a `negotiation_messages` table to support future counter-offer flows:

```
NegotiationMessage {
  id:             string
  rfp_venue_id:   string    // FK to RFP-Venue junction
  sender_type:    enum      // "organizer" | "venue"
  message_type:   enum      // "counter_offer" | "message" | "acceptance" | "rejection"
  content:        json      // structured counter (e.g., revised pricing) or free text
  created_at:     datetime
}
```

This table exists in the schema but no endpoints or UI are built at launch. When negotiation is enabled later, the comparison dashboard gains a "Negotiate" button that opens a structured back-and-forth thread.

---

## 8. Technical Approach

- **Backend:** Extends event-lifecycle-service (same as Golden Directory). New models: RFP (includes `is_template` + `template_name` fields for future use), RFPVenue (junction), VenueResponse, NegotiationMessage (schema only)
- **Background jobs:** Celery scheduled tasks for deadline processing, reminder notifications
- **Notifications:** Channel-agnostic event system → Email (Resend), WhatsApp (Africa's Talking), In-app (new notification model or extend existing agent notification system in real-time-service)
- **Currency:** Daily exchange rate cache in Redis via free API
- **API:** REST + GraphQL endpoints following existing patterns
- **Real-time:** Consider Socket.IO events for "venue just responded" live updates on the comparison dashboard

---

## 9. What This Enables Next

- **Phase 1, Section 3 (Waitlist):** If all venues are unavailable, the organizer can join waitlists
- **Phase 2 (AI Layer):** Smart match uses RFP criteria to auto-suggest venues. AI concierge creates RFPs from natural language. Autonomous monitoring watches for availability changes on shortlisted venues

---

## 10. Resolved Questions

| Question | Decision | Implementation |
|---|---|---|
| **RFP templates?** | Not at launch, but schema-ready | Add `is_template` (boolean, default false) and `template_name` (nullable text) fields to the RFP model. No UI, no endpoints — just future-proofing the schema. |
| **Venues see competitor count?** | **No.** Keep opaque | Venues see only their own RFP — no information about how many other venues received it. Transparency risks discouraging responses or encouraging artificially low pricing. |
| **Re-open closed/expired RFPs?** | **Clone, not reopen.** | Terminal states (`awarded`, `closed`, `expired`) remain terminal for clean audit trails. Add a "Duplicate RFP" action that creates a new draft pre-filled with the original's data. The organizer can modify and resend. |
| **PDF export of comparison?** | **Fast-follow, not launch.** | Will be requested by enterprise organizers sharing with procurement/leadership. Add to Phase 1.5 backlog. Use existing PDF infrastructure when built. |

## 11. Fast-Follow Backlog

Items deferred from launch but expected soon after:

1. **Negotiation UI** — counter-offer threads between organizer and venue (schema exists, Section 7)
2. **PDF export** — comparison dashboard export for stakeholder sharing
3. **Aggregate venue inbox** — cross-venue RFP view for multi-property operators
4. **RFP templates UI** — save/load templates for recurring events (schema exists)
5. **Premium rate limits** — relaxed RFP limits for paid accounts
