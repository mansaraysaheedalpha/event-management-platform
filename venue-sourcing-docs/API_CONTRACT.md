# Venue Sourcing — API Contract

**The single source of truth for frontend and backend.**
Both sides build to this contract independently. If you need to change it, both sides must agree.

---

## Conventions (Existing Patterns)

| Convention | Rule |
|---|---|
| ID format | Prefixed: `ven_` (venues), `vsp_` (spaces), `vpr_` (pricing), `vph_` (photos), `vam_` (amenities), `vac_` (amenity categories), `vvd_` (verification docs) + 12-char hex |
| REST routes | Public: `/api/v1/venues/...`, Org-scoped: `/api/v1/organizations/{orgId}/venues/...` |
| Auth (REST) | `Authorization: Bearer <jwt>` — user object has `org_id`, `sub` (userId), `user_type` |
| Auth (GraphQL) | `info.context.user["orgId"]`, `info.context.user["sub"]` |
| Field casing | snake_case (Python/REST) ↔ camelCase (GraphQL/Frontend) |
| Soft delete | `is_archived` boolean, DELETE returns 204 |
| Updates | PATCH with optional fields, only non-null values applied |
| S3 uploads | Two-step: request presigned URL → client uploads to S3 → client confirms |

---

## 1. Data Models

### 1.1 Venue (Extended — existing model enriched)

```
Venue {
  id:                 string       // "ven_" + 12hex (existing)
  organization_id:    string       // FK to org (existing)
  name:               string       // required (existing)
  address:            string?      // (existing)

  // --- NEW FIELDS ---
  slug:               string       // URL-friendly unique identifier, auto-generated from name
  description:        string?      // rich text description
  city:               string?
  country:            string?      // ISO 3166-1 alpha-2 code (e.g., "KE", "NG", "ZA")
  latitude:           float?
  longitude:          float?
  website:            string?
  phone:              string?
  email:              string?
  whatsapp:           string?

  cover_photo_id:     string?      // FK to VenuePhoto
  total_capacity:     int?         // computed from largest space, or manually set

  // Directory fields
  is_public:          boolean      // true = visible in public directory, false = org-private
  status:             VenueStatus  // "draft" | "pending_review" | "approved" | "rejected" | "suspended"
  rejection_reason:   string?      // filled when status = rejected
  submitted_at:       datetime?    // when submitted for review
  approved_at:        datetime?    // when approved
  verified:           boolean      // has passed verification
  domain_match:       boolean      // email domain matches venue website domain

  is_archived:        boolean      // (existing)
  created_at:         datetime
  updated_at:         datetime
}
```

**VenueStatus enum:** `draft`, `pending_review`, `approved`, `rejected`, `suspended`

### 1.2 VenueSpace

```
VenueSpace {
  id:                 string       // "vsp_" + 12hex
  venue_id:           string       // FK to Venue
  name:               string       // e.g., "Ballroom A"
  description:        string?
  capacity:           int?
  floor_level:        string?      // e.g., "Ground Floor", "2nd Floor"
  layout_options:     string[]     // ["theater", "classroom", "banquet", "u_shape", "boardroom", "cocktail"]
  sort_order:         int          // display ordering

  created_at:         datetime
  updated_at:         datetime
}
```

**LayoutOption enum:** `theater`, `classroom`, `banquet`, `u_shape`, `boardroom`, `cocktail`

### 1.3 VenueSpacePricing

```
VenueSpacePricing {
  id:                 string       // "vpr_" + 12hex
  space_id:           string       // FK to VenueSpace
  rate_type:          string       // "hourly" | "half_day" | "full_day"
  amount:             decimal      // price amount
  currency:           string       // ISO 4217 (e.g., "KES", "NGN", "USD", "ZAR")

  created_at:         datetime
  updated_at:         datetime
}
```

**RateType enum:** `hourly`, `half_day`, `full_day`

### 1.4 VenuePhoto

```
VenuePhoto {
  id:                 string       // "vph_" + 12hex
  venue_id:           string       // FK to Venue
  space_id:           string?      // FK to VenueSpace (null = venue-level photo)
  url:                string       // S3 public URL
  s3_key:             string       // S3 object key
  category:           string?      // "exterior" | "interior" | "rooms" | "amenities" | "catering" | "general" | null
  caption:            string?
  sort_order:         int          // display ordering
  is_cover:           boolean      // only one per venue should be true

  created_at:         datetime
}
```

**PhotoCategory enum:** `exterior`, `interior`, `rooms`, `amenities`, `catering`, `general`

### 1.5 AmenityCategory

```
AmenityCategory {
  id:                 string       // "vac_" + 12hex
  name:               string       // e.g., "Accessibility", "Technology"
  icon:               string?      // emoji or icon identifier
  sort_order:         int

  created_at:         datetime
}
```

### 1.6 Amenity

```
Amenity {
  id:                 string       // "vam_" + 12hex
  category_id:        string       // FK to AmenityCategory
  name:               string       // e.g., "Wheelchair access", "Wi-Fi"
  description:        string?
  icon:               string?      // emoji or icon identifier
  metadata_schema:    json?        // optional schema for extra data (e.g., Wi-Fi speed tier)
  sort_order:         int

  created_at:         datetime
}
```

### 1.7 VenueAmenity (Join Table)

```
VenueAmenity {
  venue_id:           string       // FK to Venue
  amenity_id:         string       // FK to Amenity
  metadata:           json?        // e.g., {"speed_tier": "high"} for Wi-Fi, {"capacity": 500} for parking

  created_at:         datetime
}
```

### 1.8 VenueVerificationDocument

```
VenueVerificationDocument {
  id:                 string       // "vvd_" + 12hex
  venue_id:           string       // FK to Venue
  document_type:      string       // "business_registration" | "utility_bill" | "tax_certificate" | "other"
  url:                string       // S3 URL
  s3_key:             string
  filename:           string       // original filename
  status:             string       // "uploaded" | "reviewed" | "accepted" | "rejected"
  admin_notes:        string?

  created_at:         datetime
  updated_at:         datetime
}
```

---

## 2. REST API Endpoints

### 2.1 Public Directory (No Auth Required)

#### `GET /api/v1/venues/directory`
Search and browse the public venue directory.

**Query Parameters:**
```
q:              string?    // free text search (name, city, address)
country:        string?    // ISO country code filter
city:           string?    // city name filter
lat:            float?     // center latitude for radius search
lng:            float?     // center longitude for radius search
radius_km:      float?     // radius in km (requires lat/lng, default: 10)
min_capacity:   int?       // minimum capacity filter
max_price:      float?     // max price (full-day rate) filter
currency:       string?    // currency for price filter (default: USD)
amenities:      string?    // comma-separated amenity IDs: "vam_abc123,vam_def456"
sort:           string?    // "recommended" | "price_asc" | "price_desc" | "capacity_desc" | "newest" (default: recommended)
page:           int?       // page number (default: 1)
page_size:      int?       // items per page (default: 12, max: 48)
```

**Response: 200**
```json
{
  "venues": [
    {
      "id": "ven_abc123def456",
      "slug": "kenyatta-international-convention-centre",
      "name": "Kenyatta International Convention Centre",
      "city": "Nairobi",
      "country": "KE",
      "address": "City Square, Nairobi",
      "latitude": -1.2864,
      "longitude": 36.8172,
      "total_capacity": 6000,
      "verified": true,
      "cover_photo_url": "https://s3.../venue-images/ven_abc123/cover.jpg",
      "space_count": 5,
      "min_price": { "amount": 25000, "currency": "KES", "rate_type": "full_day" },
      "amenity_highlights": ["Wi-Fi", "Generator", "Parking", "Catering"],
      "created_at": "2026-01-15T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 12,
    "total_count": 48,
    "total_pages": 4
  }
}
```

#### `GET /api/v1/venues/directory/{slug}`
Get a single venue's full public profile.

**Response: 200**
```json
{
  "id": "ven_abc123def456",
  "slug": "kenyatta-international-convention-centre",
  "name": "Kenyatta International Convention Centre",
  "description": "The KICC is one of the most iconic buildings in Nairobi...",
  "address": "City Square, Nairobi",
  "city": "Nairobi",
  "country": "KE",
  "latitude": -1.2864,
  "longitude": 36.8172,
  "website": "https://kicc.co.ke",
  "phone": "+254 20 332 5000",
  "email": "events@kicc.co.ke",
  "whatsapp": "+254722123456",
  "total_capacity": 6000,
  "verified": true,
  "cover_photo_url": "https://s3.../venue-images/ven_abc123/cover.jpg",
  "photos": [
    {
      "id": "vph_001",
      "url": "https://s3.../venue-images/ven_abc123/exterior1.jpg",
      "category": "exterior",
      "caption": "Main entrance",
      "is_cover": true,
      "sort_order": 0
    }
  ],
  "spaces": [
    {
      "id": "vsp_001",
      "name": "Plenary Hall",
      "description": "Main conference hall",
      "capacity": 6000,
      "floor_level": "Ground Floor",
      "layout_options": ["theater", "banquet", "cocktail"],
      "pricing": [
        { "rate_type": "full_day", "amount": 150000, "currency": "KES" },
        { "rate_type": "hourly", "amount": 20000, "currency": "KES" }
      ],
      "photos": []
    }
  ],
  "amenities": [
    {
      "id": "vam_wifi01",
      "name": "Wi-Fi",
      "category": "Technology",
      "category_icon": "📡",
      "metadata": { "speed_tier": "high" }
    }
  ],
  "listed_by": {
    "name": "KICC Management",
    "member_since": "2026-01-01T00:00:00Z"
  },
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-02-10T14:30:00Z"
}
```

#### `GET /api/v1/venues/amenities`
List all amenity categories and their amenities (for building filter UI).

**Response: 200**
```json
{
  "categories": [
    {
      "id": "vac_access01",
      "name": "Accessibility",
      "icon": "♿",
      "sort_order": 0,
      "amenities": [
        { "id": "vam_wheel01", "name": "Wheelchair access", "icon": null, "sort_order": 0 },
        { "id": "vam_elev01", "name": "Elevator", "icon": null, "sort_order": 1 }
      ]
    },
    {
      "id": "vac_tech01",
      "name": "Technology",
      "icon": "📡",
      "amenities": [
        { "id": "vam_wifi01", "name": "Wi-Fi", "metadata_schema": { "speed_tier": ["basic", "standard", "high"] }, "sort_order": 0 }
      ]
    }
  ]
}
```

#### `GET /api/v1/venues/countries`
List countries that have at least one approved venue (for country dropdown).

**Response: 200**
```json
{
  "countries": [
    { "code": "KE", "name": "Kenya", "venue_count": 45 },
    { "code": "NG", "name": "Nigeria", "venue_count": 38 },
    { "code": "ZA", "name": "South Africa", "venue_count": 22 }
  ]
}
```

#### `GET /api/v1/venues/cities`
List cities with approved venues, optionally filtered by country.

**Query Parameters:**
```
country:    string?    // ISO country code to filter by
```

**Response: 200**
```json
{
  "cities": [
    { "name": "Nairobi", "country": "KE", "venue_count": 28 },
    { "name": "Mombasa", "country": "KE", "venue_count": 12 }
  ]
}
```

---

### 2.2 Venue Owner Management (Auth Required — Venue Org)

These endpoints follow the existing pattern: `/organizations/{orgId}/venues/...`
Auth checks: JWT `org_id` must match `orgId` path param.

#### `POST /api/v1/organizations/{orgId}/venues`
Create a new venue listing (starts as draft).

**Request Body:**
```json
{
  "name": "Westlands Business Hub",
  "description": "Modern co-working and event space...",
  "address": "Westlands Road, Nairobi",
  "city": "Nairobi",
  "country": "KE",
  "latitude": -1.2673,
  "longitude": 36.8112,
  "website": "https://westlandshub.co.ke",
  "phone": "+254 20 123 4567",
  "email": "info@westlandshub.co.ke",
  "whatsapp": "+254711234567",
  "is_public": true
}
```

**Response: 201** — Full Venue object (status defaults to "draft")

#### `GET /api/v1/organizations/{orgId}/venues`
List all venues belonging to this org (including drafts, rejected, etc.).

**Query Parameters:**
```
status:     string?    // filter by status
```

**Response: 200** — Array of Venue objects

#### `GET /api/v1/organizations/{orgId}/venues/{venueId}`
Get full details of an org's venue (owner view — includes status, rejection_reason, etc.).

**Response: 200** — Full Venue object with nested spaces, photos, amenities, verification docs

#### `PATCH /api/v1/organizations/{orgId}/venues/{venueId}`
Update venue details. Only non-null fields are applied.

**Request Body:** Same fields as create, all optional.

**Response: 200** — Updated Venue object

#### `DELETE /api/v1/organizations/{orgId}/venues/{venueId}`
Archive (soft-delete) a venue.

**Response: 204**

#### `POST /api/v1/organizations/{orgId}/venues/{venueId}/submit`
Submit venue for review. Transitions status from `draft` or `rejected` to `pending_review`.

**Request Body:** (none)

**Response: 200**
```json
{
  "id": "ven_abc123",
  "status": "pending_review",
  "submitted_at": "2026-02-16T20:00:00Z"
}
```

---

### 2.3 Venue Spaces (Auth Required)

#### `POST /api/v1/organizations/{orgId}/venues/{venueId}/spaces`
Add a space to a venue.

**Request Body:**
```json
{
  "name": "Plenary Hall",
  "description": "Main conference hall with stage",
  "capacity": 6000,
  "floor_level": "Ground Floor",
  "layout_options": ["theater", "banquet", "cocktail"],
  "sort_order": 0
}
```

**Response: 201** — VenueSpace object

#### `GET /api/v1/organizations/{orgId}/venues/{venueId}/spaces`
List all spaces for a venue.

**Response: 200** — Array of VenueSpace objects with nested pricing

#### `PATCH /api/v1/organizations/{orgId}/venues/{venueId}/spaces/{spaceId}`
Update a space.

**Response: 200** — Updated VenueSpace object

#### `DELETE /api/v1/organizations/{orgId}/venues/{venueId}/spaces/{spaceId}`
Delete a space.

**Response: 204**

---

### 2.4 Space Pricing (Auth Required)

#### `PUT /api/v1/organizations/{orgId}/venues/{venueId}/spaces/{spaceId}/pricing`
Set/replace all pricing for a space (idempotent — sends full pricing array).

**Request Body:**
```json
{
  "pricing": [
    { "rate_type": "full_day", "amount": 150000, "currency": "KES" },
    { "rate_type": "hourly", "amount": 20000, "currency": "KES" }
  ]
}
```

**Response: 200** — Array of VenueSpacePricing objects

---

### 2.5 Venue Photos (Auth Required)

Uses the existing two-step presigned S3 upload pattern.

#### `POST /api/v1/organizations/{orgId}/venues/{venueId}/photos/upload-request`
Request a presigned upload URL.

**Request Body:**
```json
{
  "filename": "exterior_main.jpg",
  "content_type": "image/jpeg"
}
```

**Response: 200**
```json
{
  "upload_url": "https://s3.amazonaws.com/bucket",
  "upload_fields": { "key": "venue-images/ven_abc123/exterior_main.jpg", "...": "..." },
  "s3_key": "venue-images/ven_abc123/exterior_main.jpg"
}
```

#### `POST /api/v1/organizations/{orgId}/venues/{venueId}/photos/upload-complete`
Confirm upload and create photo record.

**Request Body:**
```json
{
  "s3_key": "venue-images/ven_abc123/exterior_main.jpg",
  "category": "exterior",
  "caption": "Main entrance",
  "is_cover": false,
  "space_id": null
}
```

**Response: 201** — VenuePhoto object

#### `PATCH /api/v1/organizations/{orgId}/venues/{venueId}/photos/{photoId}`
Update photo metadata (category, caption, sort_order, is_cover).

**Request Body:**
```json
{
  "category": "interior",
  "caption": "Updated caption",
  "sort_order": 2,
  "is_cover": true
}
```

**Response: 200** — Updated VenuePhoto

#### `DELETE /api/v1/organizations/{orgId}/venues/{venueId}/photos/{photoId}`
Delete a photo (also deletes from S3).

**Response: 204**

#### `PATCH /api/v1/organizations/{orgId}/venues/{venueId}/photos/reorder`
Reorder photos.

**Request Body:**
```json
{
  "photo_ids": ["vph_001", "vph_003", "vph_002"]
}
```

**Response: 200** — Updated array of VenuePhoto objects

---

### 2.6 Venue Amenities (Auth Required)

#### `PUT /api/v1/organizations/{orgId}/venues/{venueId}/amenities`
Set/replace all amenities for a venue (idempotent).

**Request Body:**
```json
{
  "amenities": [
    { "amenity_id": "vam_wifi01", "metadata": { "speed_tier": "high" } },
    { "amenity_id": "vam_wheel01", "metadata": null },
    { "amenity_id": "vam_generator01", "metadata": null }
  ]
}
```

**Response: 200** — Array of amenity objects with names resolved

---

### 2.7 Verification Documents (Auth Required)

#### `POST /api/v1/organizations/{orgId}/venues/{venueId}/verification/upload-request`
Request presigned URL for verification document upload.

**Request Body:**
```json
{
  "filename": "business_registration.pdf",
  "content_type": "application/pdf",
  "document_type": "business_registration"
}
```

**Response: 200** — Same pattern as photo upload (presigned URL + fields + s3_key)

#### `POST /api/v1/organizations/{orgId}/venues/{venueId}/verification/upload-complete`
Confirm verification document upload.

**Request Body:**
```json
{
  "s3_key": "venue-verification/ven_abc123/business_registration.pdf",
  "document_type": "business_registration",
  "filename": "business_registration.pdf"
}
```

**Response: 201** — VenueVerificationDocument object

#### `GET /api/v1/organizations/{orgId}/venues/{venueId}/verification`
List all verification documents for a venue.

**Response: 200** — Array of VenueVerificationDocument objects

---

### 2.8 Admin Endpoints (Auth Required — Admin Role)

#### `GET /api/v1/admin/venues`
List venues for admin review.

**Query Parameters:**
```
status:         string?    // "pending_review" | "approved" | "rejected" | "suspended"
domain_match:   boolean?   // filter by domain match
sort:           string?    // "submitted_at_asc" | "submitted_at_desc" (default: asc — oldest first)
page:           int?
page_size:      int?
```

**Response: 200** — Array of Venue objects with owner info and verification doc status

#### `POST /api/v1/admin/venues/{venueId}/approve`
Approve a venue listing.

**Request Body:** (none)

**Response: 200**
```json
{
  "id": "ven_abc123",
  "status": "approved",
  "verified": true,
  "approved_at": "2026-02-16T22:00:00Z"
}
```

#### `POST /api/v1/admin/venues/{venueId}/reject`
Reject a venue listing.

**Request Body:**
```json
{
  "reason": "Business registration document is expired. Please upload a current one."
}
```

**Response: 200**
```json
{
  "id": "ven_abc123",
  "status": "rejected",
  "rejection_reason": "Business registration document is expired..."
}
```

#### `POST /api/v1/admin/venues/{venueId}/suspend`
Suspend a venue (removes from public directory).

**Request Body:**
```json
{
  "reason": "Reported by multiple users for inaccurate information."
}
```

**Response: 200**

#### `POST /api/v1/admin/venues/{venueId}/request-documents`
Send a request for additional documents (triggers email/notification to venue owner).

**Request Body:**
```json
{
  "message": "Please upload a utility bill or tax certificate to verify your address."
}
```

**Response: 200**

#### Admin Amenity Management

#### `POST /api/v1/admin/amenity-categories`
Create a new amenity category.

**Request Body:**
```json
{ "name": "Accessibility", "icon": "♿", "sort_order": 0 }
```

**Response: 201** — AmenityCategory object

#### `POST /api/v1/admin/amenities`
Create a new amenity within a category.

**Request Body:**
```json
{ "category_id": "vac_access01", "name": "Wheelchair access", "icon": null, "sort_order": 0 }
```

**Response: 201** — Amenity object

#### `PATCH /api/v1/admin/amenities/{amenityId}`
Update an amenity.

**Response: 200**

#### `DELETE /api/v1/admin/amenities/{amenityId}`
Delete an amenity (only if no venues are using it).

**Response: 204**

---

## 3. GraphQL Schema

### 3.1 Types

```graphql
enum VenueStatus {
  DRAFT
  PENDING_REVIEW
  APPROVED
  REJECTED
  SUSPENDED
}

enum LayoutOption {
  THEATER
  CLASSROOM
  BANQUET
  U_SHAPE
  BOARDROOM
  COCKTAIL
}

enum RateType {
  HOURLY
  HALF_DAY
  FULL_DAY
}

enum PhotoCategory {
  EXTERIOR
  INTERIOR
  ROOMS
  AMENITIES
  CATERING
  GENERAL
}

type VenueType {
  id: String!
  slug: String!
  organizationId: String!
  name: String!
  description: String
  address: String
  city: String
  country: String
  latitude: Float
  longitude: Float
  website: String
  phone: String
  email: String
  whatsapp: String
  totalCapacity: Int
  coverPhotoUrl: String
  isPublic: Boolean!
  status: VenueStatus!
  rejectionReason: String
  verified: Boolean!
  domainMatch: Boolean!
  submittedAt: DateTime
  approvedAt: DateTime
  isArchived: Boolean!
  createdAt: DateTime!
  updatedAt: DateTime!

  # Nested resolvers
  spaces: [VenueSpaceType!]!
  photos: [VenuePhotoType!]!
  amenities: [VenueAmenityType!]!
  verificationDocuments: [VenueVerificationDocType!]!   # only for owner/admin
  spaceCount: Int!
  minPrice: VenuePriceType
  amenityHighlights: [String!]!                         # top 4 amenity names
  listedBy: VenueListedByType                           # resolved from organization_id (cross-service)
}

type VenueSpaceType {
  id: String!
  venueId: String!
  name: String!
  description: String
  capacity: Int
  floorLevel: String
  layoutOptions: [LayoutOption!]!
  sortOrder: Int!
  pricing: [VenueSpacePricingType!]!
  photos: [VenuePhotoType!]!
}

type VenueSpacePricingType {
  id: String!
  spaceId: String!
  rateType: RateType!
  amount: Float!
  currency: String!
}

type VenuePhotoType {
  id: String!
  venueId: String!
  spaceId: String
  url: String!
  category: PhotoCategory
  caption: String
  sortOrder: Int!
  isCover: Boolean!
  createdAt: DateTime!
}

type VenueAmenityType {
  amenityId: String!
  name: String!
  categoryName: String!
  categoryIcon: String
  metadata: JSON
}

type VenueVerificationDocType {
  id: String!
  documentType: String!
  filename: String!
  url: String!
  status: String!
  adminNotes: String
  createdAt: DateTime!
}

type VenueListedByType {
  name: String!                  # organization name
  email: String                  # owner email (only resolved for admin context, null for public)
  memberSince: DateTime!         # org created_at
}

type VenuePriceType {
  amount: Float!
  currency: String!
  rateType: RateType!
}

type AmenityCategoryType {
  id: String!
  name: String!
  icon: String
  sortOrder: Int!
  amenities: [AmenityType!]!
}

type AmenityType {
  id: String!
  categoryId: String!
  name: String!
  icon: String
  sortOrder: Int!
}

type VenueDirectoryResult {
  venues: [VenueType!]!
  totalCount: Int!
  page: Int!
  pageSize: Int!
  totalPages: Int!
}

type CountryCount {
  code: String!
  name: String!
  venueCount: Int!
}

type CityCount {
  name: String!
  country: String!
  venueCount: Int!
}
```

### 3.2 Queries

```graphql
type Query {
  # --- Public (no auth) ---
  venueDirectory(
    q: String
    country: String
    city: String
    lat: Float
    lng: Float
    radiusKm: Float
    minCapacity: Int
    maxPrice: Float
    currency: String
    amenityIds: [String!]
    sort: String
    page: Int
    pageSize: Int
  ): VenueDirectoryResult!

  venueBySlug(slug: String!): VenueType                  # public detail page

  venueAmenityCategories: [AmenityCategoryType!]!         # for filter UI

  venueCountries: [CountryCount!]!                        # for country dropdown

  venueCities(country: String): [CityCount!]!             # for city dropdown

  # --- Authenticated (venue owner) ---
  organizationVenues(status: VenueStatus): [VenueType!]!  # existing query, extended with new fields

  venue(id: ID!): VenueType                               # existing query, extended with new fields

  # --- Admin ---
  adminVenueQueue(
    status: VenueStatus
    domainMatch: Boolean
    page: Int
    pageSize: Int
  ): VenueDirectoryResult!
}
```

### 3.3 Mutations

```graphql
input VenueCreateInput {
  name: String!
  description: String
  address: String
  city: String
  country: String
  latitude: Float
  longitude: Float
  website: String
  phone: String
  email: String
  whatsapp: String
  isPublic: Boolean          # default: true
}

input VenueUpdateInput {
  name: String
  description: String
  address: String
  city: String
  country: String
  latitude: Float
  longitude: Float
  website: String
  phone: String
  email: String
  whatsapp: String
  isPublic: Boolean
}

input VenueSpaceCreateInput {
  venueId: String!
  name: String!
  description: String
  capacity: Int
  floorLevel: String
  layoutOptions: [LayoutOption!]
  sortOrder: Int
}

input VenueSpaceUpdateInput {
  name: String
  description: String
  capacity: Int
  floorLevel: String
  layoutOptions: [LayoutOption!]
  sortOrder: Int
}

input SpacePricingInput {
  rateType: RateType!
  amount: Float!
  currency: String!
}

input VenueAmenityInput {
  amenityId: String!
  metadata: JSON
}

type Mutation {
  # --- Venue CRUD (existing mutations extended) ---
  createVenue(venueIn: VenueCreateInput!): VenueType!
  updateVenue(id: String!, venueIn: VenueUpdateInput!): VenueType!
  archiveVenue(id: String!): VenueType!
  submitVenueForReview(id: String!): VenueType!

  # --- Spaces ---
  createVenueSpace(spaceIn: VenueSpaceCreateInput!): VenueSpaceType!
  updateVenueSpace(id: String!, spaceIn: VenueSpaceUpdateInput!): VenueSpaceType!
  deleteVenueSpace(id: String!): Boolean!

  # --- Pricing ---
  setSpacePricing(spaceId: String!, pricing: [SpacePricingInput!]!): [VenueSpacePricingType!]!

  # --- Amenities ---
  setVenueAmenities(venueId: String!, amenities: [VenueAmenityInput!]!): [VenueAmenityType!]!

  # --- Photos (metadata only — actual upload via REST presigned URL) ---
  updateVenuePhoto(id: String!, category: PhotoCategory, caption: String, sortOrder: Int, isCover: Boolean): VenuePhotoType!
  deleteVenuePhoto(id: String!): Boolean!
  reorderVenuePhotos(venueId: String!, photoIds: [String!]!): [VenuePhotoType!]!

  # --- Admin ---
  approveVenue(id: String!): VenueType!
  rejectVenue(id: String!, reason: String!): VenueType!
  suspendVenue(id: String!, reason: String!): VenueType!
}
```

---

## 4. File Upload Flows

### Venue Photo Upload
```
1. Frontend: POST /api/v1/organizations/{orgId}/venues/{venueId}/photos/upload-request
   → Gets: { upload_url, upload_fields, s3_key }

2. Frontend: POST directly to upload_url with upload_fields + file
   → File goes to S3: venue-images/{venueId}/{filename}

3. Frontend: POST /api/v1/organizations/{orgId}/venues/{venueId}/photos/upload-complete
   → Sends: { s3_key, category, caption, is_cover, space_id }
   → Gets: VenuePhoto record

S3 key pattern: venue-images/{venueId}/{sanitized_filename}
Max size: 10MB per photo (venue photos should be smaller than event images)
Allowed types: image/jpeg, image/png, image/webp
```

### Verification Document Upload
```
1. Frontend: POST /api/v1/organizations/{orgId}/venues/{venueId}/verification/upload-request
   → Gets: { upload_url, upload_fields, s3_key }

2. Frontend: POST directly to upload_url with upload_fields + file
   → File goes to S3: venue-verification/{venueId}/{filename}

3. Frontend: POST /api/v1/organizations/{orgId}/venues/{venueId}/verification/upload-complete
   → Sends: { s3_key, document_type, filename }
   → Gets: VenueVerificationDocument record

S3 key pattern: venue-verification/{venueId}/{sanitized_filename}
Max size: 20MB (PDFs can be larger)
Allowed types: application/pdf, image/jpeg, image/png
```

---

## 5. Auth & Permissions Summary

| Endpoint Group | Auth Required | Who Can Access |
|---|---|---|
| Public directory (`/venues/directory/*`) | No | Everyone |
| Amenity list (`/venues/amenities`) | No | Everyone |
| Venue owner CRUD (`/organizations/{orgId}/venues/*`) | Yes | Org members where `jwt.org_id == orgId` |
| Admin endpoints (`/admin/venues/*`) | Yes | Users with admin role (`jwt.is_admin == true` or superadmin) |

---

## 6. Error Responses

All errors follow this format:
```json
{
  "detail": "Human-readable error message"
}
```

| Status | When |
|---|---|
| 400 | Invalid input (validation failure) |
| 401 | Missing or invalid JWT |
| 403 | JWT valid but user doesn't have permission (wrong org, not admin) |
| 404 | Resource not found |
| 409 | Conflict (e.g., slug already taken, max 10 photos reached) |
| 422 | Unprocessable entity (e.g., submitting venue with no spaces) |
