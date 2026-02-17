# Venue Sourcing — RFP System API Contract

**The single source of truth for frontend and backend.**
Both sides build to this contract independently. If you need to change it, both sides must agree.

**Depends on:** Golden Directory API Contract — venues, spaces, amenities must exist

---

## Conventions (Same as Golden Directory + New Prefixes)

| Convention | Rule |
|---|---|
| ID format | Prefixed: `rfp_` (RFPs), `rfv_` (RFP-venue junction), `vrs_` (venue responses), `ngm_` (negotiation messages) + 12-char hex |
| REST routes | Org-scoped: `/api/v1/organizations/{orgId}/rfps/...`, Venue-scoped: `/api/v1/venues/{venueId}/rfps/...` |
| Auth (REST) | `Authorization: Bearer <jwt>` — user object has `org_id`, `sub` (userId), `user_type` |
| Auth (GraphQL) | `info.context.user["orgId"]`, `info.context.user["sub"]` |
| Field casing | snake_case (Python/REST) ↔ camelCase (GraphQL/Frontend) |
| Updates | PATCH with optional fields, only non-null values applied |
| Rate limiting | Max 5 active RFPs per organizer, max 10 venues per RFP |

---

## 1. Data Models

### 1.1 RFP

```
RFP {
  id:                     string       // "rfp_" + 12hex
  organization_id:        string       // FK to org (the organizer)
  title:                  string       // required, e.g., "Annual Tech Conference 2026 Venue"
  event_type:             EventType    // enum
  attendance_min:         int          // min expected headcount
  attendance_max:         int          // max expected headcount
  preferred_dates_start:  date?        // start of date range (null if flexible)
  preferred_dates_end:    date?        // end of date range (null if flexible)
  dates_flexible:         boolean      // true = "flexible within these weeks"
  duration:               string       // free text: "2 full days", "4 hours"
  space_requirements:     string[]     // layout types: ["theater", "classroom", "banquet"]
  required_amenity_ids:   string[]     // amenity IDs from Golden Directory
  catering_needs:         CateringNeed // enum
  budget_min:             decimal?     // optional
  budget_max:             decimal?     // optional
  budget_currency:        string?      // ISO 4217, e.g., "USD"
  preferred_currency:     string       // for comparison dashboard display, default "USD"
  additional_notes:       text?        // free text
  response_deadline:      datetime     // when venues must respond by
  linked_event_id:        string?      // optional FK to Event

  status:                 RFPStatus    // enum
  sent_at:                datetime?    // when the RFP was dispatched
  is_template:            boolean      // default false (schema-ready, no UI)
  template_name:          string?      // nullable (schema-ready, no UI)

  created_at:             datetime
  updated_at:             datetime
}
```

**EventType enum:** `conference`, `wedding`, `corporate_retreat`, `workshop`, `exhibition`, `social_event`, `other`

**CateringNeed enum:** `none`, `in_house_preferred`, `external_allowed`, `no_preference`

**RFPStatus enum:** `draft`, `sent`, `collecting_responses`, `review`, `awarded`, `closed`, `expired`

### 1.2 RFPVenue (Junction Table)

```
RFPVenue {
  id:                     string       // "rfv_" + 12hex
  rfp_id:                 string       // FK to RFP
  venue_id:               string       // FK to Venue (Golden Directory)
  status:                 RFPVenueStatus // enum

  // Tracking timestamps
  notified_at:            datetime?    // when notification was sent
  viewed_at:              datetime?    // when venue first opened the RFP
  responded_at:           datetime?    // when venue submitted response

  // Pre-computed fit indicators (snapshotted at send time)
  capacity_fit:           string?      // "good_fit" | "tight_fit" | "oversized" | "poor_fit"
  amenity_match_pct:      float?       // 0-100 percentage

  created_at:             datetime
  updated_at:             datetime
}
```

**RFPVenueStatus enum:** `received`, `viewed`, `responded`, `shortlisted`, `awarded`, `declined`, `no_response`

### 1.3 VenueResponse (Pricing Snapshot)

```
VenueResponse {
  id:                     string       // "vrs_" + 12hex
  rfp_venue_id:           string       // FK to RFPVenue (unique — one response per venue per RFP)

  availability:           Availability // enum
  proposed_space_id:      string?      // FK to VenueSpace (reference only)
  proposed_space_name:    string       // denormalized snapshot
  proposed_space_capacity: int?        // denormalized snapshot

  // All pricing in venue's chosen currency
  currency:               string       // ISO 4217 — single currency for all pricing in this response
  space_rental_price:     decimal?     // per-day or per-event
  catering_price_per_head: decimal?
  av_equipment_fees:      decimal?
  setup_cleanup_fees:     decimal?
  other_fees:             decimal?
  other_fees_description: string?

  // Amenity details
  included_amenity_ids:   string[]     // amenity IDs included at no extra cost
  extra_cost_amenities:   json         // [{ "amenity_id": "vam_x", "name": "Wi-Fi", "price": 5000 }]

  // Terms
  cancellation_policy:    text?
  deposit_amount:         decimal?
  payment_schedule:       text?        // e.g., "50% deposit, 50% 7 days before event"
  alternative_dates:      json?        // ["2026-03-15", "2026-03-22"] if original dates unavailable
  quote_valid_until:      date?
  notes:                  text?

  // Calculated
  total_estimated_cost:   decimal      // auto-sum of all pricing fields

  created_at:             datetime
  updated_at:             datetime
}
```

**Availability enum:** `confirmed`, `tentative`, `unavailable`

### 1.4 NegotiationMessage (Schema Only — No Endpoints at Launch)

```
NegotiationMessage {
  id:                     string       // "ngm_" + 12hex
  rfp_venue_id:           string       // FK to RFPVenue
  sender_type:            string       // "organizer" | "venue"
  message_type:           string       // "counter_offer" | "message" | "acceptance" | "rejection"
  content:                json         // structured counter or free text
  created_at:             datetime
}
```

---

## 2. REST API Endpoints

### 2.1 Organizer RFP Management (Auth Required — Org Member)

Auth: JWT `org_id` must match `orgId` path param.

#### `POST /api/v1/organizations/{orgId}/rfps`
Create a new draft RFP.

**Rate limit:** Max 5 active RFPs per organizer. Return 429 if exceeded.

**Request Body:**
```json
{
  "title": "Annual Tech Conference 2026 Venue",
  "event_type": "conference",
  "attendance_min": 200,
  "attendance_max": 300,
  "preferred_dates_start": "2026-06-15",
  "preferred_dates_end": "2026-06-17",
  "dates_flexible": false,
  "duration": "2 full days",
  "space_requirements": ["theater", "classroom"],
  "required_amenity_ids": ["vam_wifi01", "vam_projector01", "vam_parking01"],
  "catering_needs": "in_house_preferred",
  "budget_min": 500000,
  "budget_max": 1500000,
  "budget_currency": "KES",
  "preferred_currency": "KES",
  "additional_notes": "Need wheelchair accessibility and backup power",
  "response_deadline": "2026-02-23T23:59:59Z",
  "linked_event_id": null
}
```

**Response: 201** — Full RFP object (status = "draft")

#### `GET /api/v1/organizations/{orgId}/rfps`
List organizer's RFPs.

**Query Parameters:**
```
status:     string?    // filter by status
page:       int?       // default: 1
page_size:  int?       // default: 10, max: 50
```

**Response: 200**
```json
{
  "rfps": [
    {
      "id": "rfp_abc123def456",
      "title": "Annual Tech Conference 2026 Venue",
      "event_type": "conference",
      "status": "collecting_responses",
      "attendance_max": 300,
      "preferred_dates_start": "2026-06-15",
      "response_deadline": "2026-02-23T23:59:59Z",
      "venue_count": 5,
      "response_count": 3,
      "sent_at": "2026-02-16T10:00:00Z",
      "created_at": "2026-02-15T14:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total_count": 12,
    "total_pages": 2
  }
}
```

#### `GET /api/v1/organizations/{orgId}/rfps/{rfpId}`
Get RFP detail with all venue statuses.

**Response: 200**
```json
{
  "id": "rfp_abc123def456",
  "title": "Annual Tech Conference 2026 Venue",
  "event_type": "conference",
  "attendance_min": 200,
  "attendance_max": 300,
  "preferred_dates_start": "2026-06-15",
  "preferred_dates_end": "2026-06-17",
  "dates_flexible": false,
  "duration": "2 full days",
  "space_requirements": ["theater", "classroom"],
  "required_amenities": [
    { "id": "vam_wifi01", "name": "Wi-Fi", "category": "Technology" },
    { "id": "vam_projector01", "name": "Projector", "category": "Technology" }
  ],
  "catering_needs": "in_house_preferred",
  "budget_min": 500000,
  "budget_max": 1500000,
  "budget_currency": "KES",
  "preferred_currency": "KES",
  "additional_notes": "Need wheelchair accessibility and backup power",
  "response_deadline": "2026-02-23T23:59:59Z",
  "linked_event_id": null,
  "status": "collecting_responses",
  "sent_at": "2026-02-16T10:00:00Z",
  "venues": [
    {
      "id": "rfv_venue01",
      "venue_id": "ven_kicc001",
      "venue_name": "KICC Nairobi",
      "venue_slug": "kenyatta-international-convention-centre",
      "venue_city": "Nairobi",
      "venue_country": "KE",
      "venue_verified": true,
      "venue_cover_photo_url": "https://s3.../cover.jpg",
      "status": "responded",
      "capacity_fit": "good_fit",
      "amenity_match_pct": 85.0,
      "notified_at": "2026-02-16T10:00:05Z",
      "viewed_at": "2026-02-16T12:30:00Z",
      "responded_at": "2026-02-17T09:00:00Z",
      "has_response": true
    }
  ],
  "created_at": "2026-02-15T14:00:00Z",
  "updated_at": "2026-02-17T09:00:00Z"
}
```

#### `PATCH /api/v1/organizations/{orgId}/rfps/{rfpId}`
Update a draft RFP. Only allowed when status = `draft`.

**Request Body:** Same fields as create, all optional.

**Response: 200** — Updated RFP object

#### `DELETE /api/v1/organizations/{orgId}/rfps/{rfpId}`
Delete a draft RFP. Only allowed when status = `draft`.

**Response: 204**

---

### 2.2 RFP Venue Selection (Auth Required)

#### `POST /api/v1/organizations/{orgId}/rfps/{rfpId}/venues`
Add venues to a draft RFP.

**Validation:** Max 10 venues per RFP. RFP must be in `draft` state.

**Request Body:**
```json
{
  "venue_ids": ["ven_kicc001", "ven_eko002", "ven_serena003"]
}
```

**Response: 201**
```json
{
  "added": [
    {
      "id": "rfv_001",
      "venue_id": "ven_kicc001",
      "venue_name": "KICC Nairobi",
      "capacity_fit": "good_fit",
      "amenity_match_pct": 85.0,
      "status": "received"
    }
  ],
  "skipped": []
}
```

#### `DELETE /api/v1/organizations/{orgId}/rfps/{rfpId}/venues/{venueId}`
Remove a venue from a draft RFP. Only allowed when status = `draft`.

**Response: 204**

#### `GET /api/v1/organizations/{orgId}/rfps/{rfpId}/pre-send-summary`
Get pre-send fit indicators for all selected venues. Called before sending to help organizer review venue fit.

**Response: 200**
```json
{
  "rfp_id": "rfp_abc123",
  "venue_count": 3,
  "venues": [
    {
      "venue_id": "ven_kicc001",
      "venue_name": "KICC Nairobi",
      "venue_capacity": 6000,
      "capacity_fit": "oversized",
      "capacity_fit_color": "yellow",
      "amenity_match_pct": 85.0,
      "amenity_match_color": "green",
      "matched_amenities": ["Wi-Fi", "Projector"],
      "missing_amenities": ["Parking"],
      "price_indicator": "within_budget",
      "price_indicator_detail": "Full-day rate: KES 150,000 (budget: KES 500,000 - 1,500,000)"
    }
  ]
}
```

---

### 2.3 RFP Actions (Auth Required)

#### `POST /api/v1/organizations/{orgId}/rfps/{rfpId}/send`
Send RFP to all selected venues. Triggers notifications via Email + WhatsApp + In-app.

**Validation:**
- RFP must be in `draft` state
- Must have at least 1 venue selected
- Response deadline must be in the future

**Request Body:** (none)

**Response: 200**
```json
{
  "id": "rfp_abc123",
  "status": "sent",
  "sent_at": "2026-02-16T10:00:00Z",
  "venues_notified": 5
}
```

#### `POST /api/v1/organizations/{orgId}/rfps/{rfpId}/extend-deadline`
Extend the response deadline.

**Validation:** RFP must be in `sent` or `collecting_responses` state. New deadline must be after current deadline.

**Request Body:**
```json
{
  "new_deadline": "2026-02-26T23:59:59Z"
}
```

**Response: 200** — Updated RFP object

#### `POST /api/v1/organizations/{orgId}/rfps/{rfpId}/close`
Close RFP without awarding. Allowed from `sent`, `collecting_responses`, or `review` state.

**Request Body:**
```json
{
  "reason": "Decided to postpone the event"
}
```

**Response: 200** — Updated RFP object with status = "closed"

#### `POST /api/v1/organizations/{orgId}/rfps/{rfpId}/duplicate`
Clone an RFP to a new draft. Works from any state.

**Response: 201** — New RFP object (status = "draft", no venues attached, new deadline set to 7 days from now)

---

### 2.4 Venue Decision Actions (Auth Required)

#### `POST /api/v1/organizations/{orgId}/rfps/{rfpId}/venues/{rfvId}/shortlist`
Shortlist a venue. Allowed when venue status is `responded`.

**Response: 200** — Updated RFPVenue object

#### `POST /api/v1/organizations/{orgId}/rfps/{rfpId}/venues/{rfvId}/award`
Award the RFP to a venue. Only one venue can be awarded per RFP. Triggers notification to venue.

**Validation:** Venue must be in `responded` or `shortlisted` state. No other venue already awarded on this RFP.

**Response: 200** — Updated RFPVenue object. RFP status transitions to `awarded`.

#### `POST /api/v1/organizations/{orgId}/rfps/{rfpId}/venues/{rfvId}/decline`
Decline a venue's proposal. Triggers notification to venue.

**Request Body:**
```json
{
  "reason": "Budget exceeded our range"
}
```

**Response: 200** — Updated RFPVenue object

---

### 2.5 Comparison Dashboard (Auth Required)

#### `GET /api/v1/organizations/{orgId}/rfps/{rfpId}/compare`
Get structured comparison data for all venue responses. Only returns venues that have responded.

**Response: 200**
```json
{
  "rfp_id": "rfp_abc123",
  "preferred_currency": "KES",
  "exchange_rates": {
    "base": "KES",
    "rates": { "USD": 0.0078, "NGN": 12.15, "SLE": 0.17 },
    "fetched_at": "2026-02-16T00:00:00Z"
  },
  "required_amenity_count": 3,
  "venues": [
    {
      "rfv_id": "rfv_001",
      "venue_id": "ven_kicc001",
      "venue_name": "KICC Nairobi",
      "venue_verified": true,
      "venue_slug": "kenyatta-international-convention-centre",
      "status": "responded",
      "response": {
        "id": "vrs_001",
        "availability": "confirmed",
        "proposed_space_name": "Plenary Hall",
        "proposed_space_capacity": 6000,
        "currency": "KES",
        "space_rental_price": 150000,
        "catering_price_per_head": 2500,
        "av_equipment_fees": 50000,
        "setup_cleanup_fees": 25000,
        "other_fees": null,
        "total_estimated_cost": 975000,
        "total_in_preferred_currency": 975000,
        "included_amenity_ids": ["vam_wifi01", "vam_projector01"],
        "extra_cost_amenities": [
          { "amenity_id": "vam_parking01", "name": "Parking", "price": 10000 }
        ],
        "deposit_amount": 300000,
        "quote_valid_until": "2026-03-15",
        "cancellation_policy": "Full refund before 30 days, 50% before 14 days, no refund after",
        "created_at": "2026-02-17T09:00:00Z"
      },
      "amenity_match_pct": 66.7,
      "response_time_hours": 23.0,
      "badges": ["best_value"]
    }
  ],
  "badges": {
    "best_value": "rfv_001",
    "best_match": "rfv_003"
  }
}
```

---

### 2.6 Venue Owner RFP Endpoints (Auth Required — Venue Org)

Auth: JWT `org_id` must match the venue's `organization_id`.

#### `GET /api/v1/venues/{venueId}/rfps`
RFP inbox — list all RFPs received by this venue.

**Query Parameters:**
```
status:     string?    // filter by venue response status
page:       int?       // default: 1
page_size:  int?       // default: 10
```

**Response: 200**
```json
{
  "rfps": [
    {
      "rfv_id": "rfv_001",
      "rfp_id": "rfp_abc123",
      "title": "Annual Tech Conference 2026 Venue",
      "event_type": "conference",
      "organizer_name": "TechCo Events",
      "attendance_range": "200-300",
      "preferred_dates": "Jun 15-17, 2026",
      "status": "received",
      "response_deadline": "2026-02-23T23:59:59Z",
      "received_at": "2026-02-16T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total_count": 3,
    "total_pages": 1
  }
}
```

#### `GET /api/v1/venues/{venueId}/rfps/{rfpId}`
View RFP details. **Side effect:** transitions venue status from `received` → `viewed` on first access.

**Response: 200**
```json
{
  "rfv_id": "rfv_001",
  "rfp_id": "rfp_abc123",
  "title": "Annual Tech Conference 2026 Venue",
  "event_type": "conference",
  "attendance_min": 200,
  "attendance_max": 300,
  "preferred_dates_start": "2026-06-15",
  "preferred_dates_end": "2026-06-17",
  "dates_flexible": false,
  "duration": "2 full days",
  "space_requirements": ["theater", "classroom"],
  "required_amenities": [
    { "id": "vam_wifi01", "name": "Wi-Fi", "category": "Technology" },
    { "id": "vam_projector01", "name": "Projector", "category": "Technology" },
    { "id": "vam_parking01", "name": "Parking", "category": "Infrastructure" }
  ],
  "catering_needs": "in_house_preferred",
  "additional_notes": "Need wheelchair accessibility and backup power",
  "response_deadline": "2026-02-23T23:59:59Z",
  "status": "viewed",
  "venue_spaces": [
    {
      "id": "vsp_001",
      "name": "Plenary Hall",
      "capacity": 6000,
      "layout_options": ["theater", "banquet", "cocktail"]
    }
  ],
  "existing_response": null
}
```

#### `POST /api/v1/venues/{venueId}/rfps/{rfpId}/respond`
Submit a structured response to an RFP.

**Validation:**
- Venue status must be `received` or `viewed`
- Response deadline must not have passed
- One response per venue per RFP

**Request Body:**
```json
{
  "availability": "confirmed",
  "proposed_space_id": "vsp_001",
  "currency": "KES",
  "space_rental_price": 150000,
  "catering_price_per_head": 2500,
  "av_equipment_fees": 50000,
  "setup_cleanup_fees": 25000,
  "other_fees": null,
  "other_fees_description": null,
  "included_amenity_ids": ["vam_wifi01", "vam_projector01"],
  "extra_cost_amenities": [
    { "amenity_id": "vam_parking01", "name": "Parking", "price": 10000 }
  ],
  "cancellation_policy": "Full refund before 30 days, 50% before 14 days, no refund after",
  "deposit_amount": 300000,
  "payment_schedule": "50% deposit, 50% 7 days before event",
  "alternative_dates": null,
  "quote_valid_until": "2026-03-15",
  "notes": "We can also provide event coordination services"
}
```

**Response: 201** — VenueResponse object

**Side effects:**
- Venue status transitions to `responded`
- `responded_at` timestamp set
- If first response on this RFP → RFP status transitions `sent` → `collecting_responses`
- If all venues have now responded → RFP status transitions to `review`
- Notification sent to organizer: "Venue X has responded to your RFP"
- `total_estimated_cost` auto-calculated (sum of all pricing fields + catering * attendance_max)
- `proposed_space_name` and `proposed_space_capacity` denormalized from the space record

---

### 2.7 Exchange Rate API

#### `GET /api/v1/exchange-rates`
Get current cached exchange rates. Used by the comparison dashboard frontend.

**Query Parameters:**
```
base:       string     // base currency, e.g., "KES"
targets:    string?    // comma-separated target currencies, e.g., "USD,NGN,SLE" (if omitted, returns all)
```

**Response: 200**
```json
{
  "base": "KES",
  "rates": {
    "USD": 0.0078,
    "NGN": 12.15,
    "SLE": 0.17,
    "ZAR": 0.14,
    "GHS": 0.12
  },
  "fetched_at": "2026-02-16T00:00:00Z",
  "source": "exchangerate-api.com"
}
```

---

## 3. GraphQL Schema

### 3.1 Enums

```graphql
enum EventType {
  CONFERENCE
  WEDDING
  CORPORATE_RETREAT
  WORKSHOP
  EXHIBITION
  SOCIAL_EVENT
  OTHER
}

enum CateringNeed {
  NONE
  IN_HOUSE_PREFERRED
  EXTERNAL_ALLOWED
  NO_PREFERENCE
}

enum RFPStatus {
  DRAFT
  SENT
  COLLECTING_RESPONSES
  REVIEW
  AWARDED
  CLOSED
  EXPIRED
}

enum RFPVenueStatus {
  RECEIVED
  VIEWED
  RESPONDED
  SHORTLISTED
  AWARDED
  DECLINED
  NO_RESPONSE
}

enum Availability {
  CONFIRMED
  TENTATIVE
  UNAVAILABLE
}

enum CapacityFit {
  GOOD_FIT
  TIGHT_FIT
  OVERSIZED
  POOR_FIT
}
```

### 3.2 Types

```graphql
type RFPType {
  id: String!
  organizationId: String!
  title: String!
  eventType: EventType!
  attendanceMin: Int!
  attendanceMax: Int!
  preferredDatesStart: Date
  preferredDatesEnd: Date
  datesFlexible: Boolean!
  duration: String!
  spaceRequirements: [String!]!
  requiredAmenities: [RFPAmenityType!]!        # resolved amenity names
  cateringNeeds: CateringNeed!
  budgetMin: Float
  budgetMax: Float
  budgetCurrency: String
  preferredCurrency: String!
  additionalNotes: String
  responseDeadline: DateTime!
  linkedEventId: String
  status: RFPStatus!
  sentAt: DateTime
  createdAt: DateTime!
  updatedAt: DateTime!

  # Nested resolvers
  venues: [RFPVenueType!]!                     # all venue junctions
  venueCount: Int!
  responseCount: Int!
}

type RFPAmenityType {
  id: String!
  name: String!
  category: String!
}

type RFPVenueType {
  id: String!                                   # rfv_ ID
  rfpId: String!
  venueId: String!
  venueName: String!
  venueSlug: String!
  venueCity: String
  venueCountry: String
  venueVerified: Boolean!
  venueCoverPhotoUrl: String
  status: RFPVenueStatus!
  capacityFit: CapacityFit
  amenityMatchPct: Float
  notifiedAt: DateTime
  viewedAt: DateTime
  respondedAt: DateTime
  hasResponse: Boolean!

  # Nested resolver (only if responded)
  response: VenueResponseType
}

type VenueResponseType {
  id: String!
  availability: Availability!
  proposedSpaceName: String!
  proposedSpaceCapacity: Int
  currency: String!
  spaceRentalPrice: Float
  cateringPricePerHead: Float
  avEquipmentFees: Float
  setupCleanupFees: Float
  otherFees: Float
  otherFeesDescription: String
  totalEstimatedCost: Float!
  includedAmenityIds: [String!]!
  extraCostAmenities: [ExtraCostAmenityType!]!
  cancellationPolicy: String
  depositAmount: Float
  paymentSchedule: String
  alternativeDates: [String!]
  quoteValidUntil: Date
  notes: String
  createdAt: DateTime!
}

type ExtraCostAmenityType {
  amenityId: String!
  name: String!
  price: Float!
}

type ComparisonDashboardType {
  rfpId: String!
  preferredCurrency: String!
  exchangeRates: ExchangeRateType
  requiredAmenityCount: Int!
  venues: [ComparisonVenueType!]!
  badges: ComparisonBadgesType!
}

type ComparisonVenueType {
  rfvId: String!
  venueId: String!
  venueName: String!
  venueVerified: Boolean!
  venueSlug: String!
  status: RFPVenueStatus!
  response: VenueResponseType!
  totalInPreferredCurrency: Float!
  amenityMatchPct: Float!
  responseTimeHours: Float!
  badges: [String!]!
}

type ComparisonBadgesType {
  bestValue: String                             # rfv_id or null
  bestMatch: String                             # rfv_id or null
}

type ExchangeRateType {
  base: String!
  rates: JSON!
  fetchedAt: DateTime!
}

type RFPListResult {
  rfps: [RFPType!]!
  totalCount: Int!
  page: Int!
  pageSize: Int!
  totalPages: Int!
}

# Venue owner's view of an RFP
type VenueRFPInboxItem {
  rfvId: String!
  rfpId: String!
  title: String!
  eventType: EventType!
  organizerName: String!
  attendanceRange: String!
  preferredDates: String!
  status: RFPVenueStatus!
  responseDeadline: DateTime!
  receivedAt: DateTime!
}

type VenueRFPDetail {
  rfvId: String!
  rfpId: String!
  title: String!
  eventType: EventType!
  attendanceMin: Int!
  attendanceMax: Int!
  preferredDatesStart: Date
  preferredDatesEnd: Date
  datesFlexible: Boolean!
  duration: String!
  spaceRequirements: [String!]!
  requiredAmenities: [RFPAmenityType!]!
  cateringNeeds: CateringNeed!
  additionalNotes: String
  responseDeadline: DateTime!
  status: RFPVenueStatus!
  venueSpaces: [VenueSpaceType!]!               # the venue's own spaces for selection
  existingResponse: VenueResponseType           # null if not yet responded
}

type VenueRFPInboxResult {
  rfps: [VenueRFPInboxItem!]!
  totalCount: Int!
  page: Int!
  pageSize: Int!
  totalPages: Int!
}

type PreSendVenueFit {
  venueId: String!
  venueName: String!
  venueCapacity: Int
  capacityFit: CapacityFit!
  capacityFitColor: String!
  amenityMatchPct: Float!
  amenityMatchColor: String!
  matchedAmenities: [String!]!
  missingAmenities: [String!]!
  priceIndicator: String!
  priceIndicatorDetail: String
}

type PreSendSummary {
  rfpId: String!
  venueCount: Int!
  venues: [PreSendVenueFit!]!
}
```

### 3.3 Queries

```graphql
type Query {
  # --- Organizer (auth required) ---
  organizationRFPs(
    status: RFPStatus
    page: Int
    pageSize: Int
  ): RFPListResult!

  rfp(id: String!): RFPType                    # full RFP detail with venues

  rfpComparison(rfpId: String!): ComparisonDashboardType!

  rfpPreSendSummary(rfpId: String!): PreSendSummary!

  # --- Venue Owner (auth required) ---
  venueRFPInbox(
    venueId: String!
    status: RFPVenueStatus
    page: Int
    pageSize: Int
  ): VenueRFPInboxResult!

  venueRFPDetail(
    venueId: String!
    rfpId: String!
  ): VenueRFPDetail                             # side effect: marks as viewed

  # --- Utility ---
  exchangeRates(
    base: String!
    targets: [String!]
  ): ExchangeRateType!
}
```

### 3.4 Mutations

```graphql
input RFPCreateInput {
  title: String!
  eventType: EventType!
  attendanceMin: Int!
  attendanceMax: Int!
  preferredDatesStart: Date
  preferredDatesEnd: Date
  datesFlexible: Boolean
  duration: String!
  spaceRequirements: [String!]
  requiredAmenityIds: [String!]
  cateringNeeds: CateringNeed!
  budgetMin: Float
  budgetMax: Float
  budgetCurrency: String
  preferredCurrency: String
  additionalNotes: String
  responseDeadline: DateTime!
  linkedEventId: String
}

input RFPUpdateInput {
  title: String
  eventType: EventType
  attendanceMin: Int
  attendanceMax: Int
  preferredDatesStart: Date
  preferredDatesEnd: Date
  datesFlexible: Boolean
  duration: String
  spaceRequirements: [String!]
  requiredAmenityIds: [String!]
  cateringNeeds: CateringNeed
  budgetMin: Float
  budgetMax: Float
  budgetCurrency: String
  preferredCurrency: String
  additionalNotes: String
  responseDeadline: DateTime
  linkedEventId: String
}

input VenueResponseInput {
  availability: Availability!
  proposedSpaceId: String
  currency: String!
  spaceRentalPrice: Float
  cateringPricePerHead: Float
  avEquipmentFees: Float
  setupCleanupFees: Float
  otherFees: Float
  otherFeesDescription: String
  includedAmenityIds: [String!]
  extraCostAmenities: [ExtraCostAmenityInput!]
  cancellationPolicy: String
  depositAmount: Float
  paymentSchedule: String
  alternativeDates: [String!]
  quoteValidUntil: Date
  notes: String
}

input ExtraCostAmenityInput {
  amenityId: String!
  name: String!
  price: Float!
}

type Mutation {
  # --- Organizer RFP Management ---
  createRFP(input: RFPCreateInput!): RFPType!
  updateRFP(id: String!, input: RFPUpdateInput!): RFPType!
  deleteRFP(id: String!): Boolean!

  addVenuesToRFP(rfpId: String!, venueIds: [String!]!): [RFPVenueType!]!
  removeVenueFromRFP(rfpId: String!, venueId: String!): Boolean!

  sendRFP(id: String!): RFPType!
  extendRFPDeadline(id: String!, newDeadline: DateTime!): RFPType!
  closeRFP(id: String!, reason: String): RFPType!
  duplicateRFP(id: String!): RFPType!

  # --- Venue Decision ---
  shortlistVenue(rfpId: String!, rfvId: String!): RFPVenueType!
  awardVenue(rfpId: String!, rfvId: String!): RFPVenueType!
  declineVenue(rfpId: String!, rfvId: String!, reason: String): RFPVenueType!

  # --- Venue Owner Response ---
  submitVenueResponse(
    venueId: String!
    rfpId: String!
    input: VenueResponseInput!
  ): VenueResponseType!
}
```

---

## 4. Notification Events

These are internal system events that trigger multi-channel delivery. The backend emits these; delivery adapters handle channel routing.

| Event Key | Recipient | Channels | Trigger |
|---|---|---|---|
| `rfp.new_request` | Venue owner | In-app + Email + WhatsApp | RFP sent |
| `rfp.deadline_reminder` | Venue owner (non-responders) | Email + WhatsApp | 24h before deadline (Celery scheduled) |
| `rfp.venue_responded` | Organizer | In-app + Email | Venue submits response |
| `rfp.all_responded` | Organizer | In-app + Email | All venues responded |
| `rfp.deadline_passed` | Organizer | In-app + Email | Deadline expires (Celery scheduled) |
| `rfp.proposal_accepted` | Venue owner | In-app + Email + WhatsApp | Organizer awards venue |
| `rfp.proposal_declined` | Venue owner | In-app + Email | Organizer declines venue |
| `rfp.deadline_extended` | Venue owner (non-responders) | Email + WhatsApp | Organizer extends deadline |

---

## 5. Background Jobs (Celery)

| Task | Schedule | Description |
|---|---|---|
| `process_rfp_deadline` | Runs every 5 minutes | Checks for RFPs past deadline. Transitions status, marks `no_response` venues, notifies organizer |
| `send_rfp_deadline_reminders` | Runs every hour | Sends 24h-before reminders to non-responding venues |
| `refresh_exchange_rates` | Runs daily at 00:00 UTC | Fetches exchange rates and caches in Redis (TTL: 25 hours) |

---

## 6. Auth & Permissions Summary

| Endpoint Group | Auth Required | Who Can Access |
|---|---|---|
| Organizer RFP CRUD (`/organizations/{orgId}/rfps/*`) | Yes | Org members where `jwt.org_id == orgId` |
| Venue RFP inbox (`/venues/{venueId}/rfps/*`) | Yes | Org members who own the venue (`venue.organization_id == jwt.org_id`) |
| Exchange rates (`/exchange-rates`) | No | Everyone (cached, public data) |

---

## 7. Error Responses

All errors follow this format:
```json
{
  "detail": "Human-readable error message"
}
```

| Status | When |
|---|---|
| 400 | Invalid input (validation failure, invalid amenity IDs, invalid dates) |
| 401 | Missing or invalid JWT |
| 403 | JWT valid but user doesn't have permission (wrong org, venue not owned) |
| 404 | RFP, venue, or RFP-venue junction not found |
| 409 | Conflict (max 10 venues, venue already added, already responded, already awarded) |
| 422 | Invalid state transition (e.g., sending a non-draft RFP, responding after deadline) |
| 429 | Rate limited (max 5 active RFPs per organizer) |
