# Venue Sourcing — Backend Implementation Tasks

**Service:** `event-lifecycle-service` (Python/FastAPI/SQLAlchemy)
**Reference:** [API_CONTRACT.md](API_CONTRACT.md) — build exactly to this contract
**Reference:** [VENUE_SOURCING_GOLDEN_DIRECTORY_SPEC.md](../VENUE_SOURCING_GOLDEN_DIRECTORY_SPEC.md) — feature spec

---

## Task B1: Database Models & Migration

**Files to create/modify:**

- `app/models/venue.py` — EXTEND existing model with new columns
- `app/models/venue_space.py` — NEW
- `app/models/venue_space_pricing.py` — NEW
- `app/models/venue_photo.py` — NEW
- `app/models/amenity_category.py` — NEW
- `app/models/amenity.py` — NEW
- `app/models/venue_amenity.py` — NEW (join table)
- `app/models/venue_verification_document.py` — NEW
- `app/models/__init__.py` — register new models
- `alembic/versions/xxx_venue_sourcing.py` — NEW migration

**What to do:**

1. Extend `Venue` model with all new columns from API contract section 1.1:
   - `slug` (unique, indexed), `description`, `city`, `country` (indexed), `latitude`, `longitude`
   - `website`, `phone`, `email`, `whatsapp`
   - `cover_photo_id`, `total_capacity`
   - `is_public` (default False), `status` (enum, default 'draft'), `rejection_reason`
   - `submitted_at`, `approved_at`, `verified` (default False), `domain_match` (default False)
   - `created_at`, `updated_at` (with `onupdate`)

2. Create all new models matching API contract sections 1.2 through 1.8

3. ID generation: use the existing pattern from `venue.py` — `ven_` prefix + 12-char hex. Apply same pattern with new prefixes: `vsp_`, `vpr_`, `vph_`, `vac_`, `vam_`, `vvd_`

4. Add relationships:
   - `Venue.spaces` → `VenueSpace` (one-to-many, cascade delete)
   - `Venue.photos` → `VenuePhoto` (one-to-many, cascade delete)
   - `Venue.amenities` → `VenueAmenity` (one-to-many, cascade delete)
   - `Venue.verification_documents` → `VenueVerificationDocument` (one-to-many)
   - `VenueSpace.pricing` → `VenueSpacePricing` (one-to-many, cascade delete)
   - `VenueSpace.photos` → `VenuePhoto` (one-to-many via `space_id`)

5. Create Alembic migration. Include seed data for amenity categories and amenities:

**Seed Amenity Categories & Amenities:**
```
Accessibility: Wheelchair access, Elevator, Accessible restrooms, Braille signage
Technology: Wi-Fi, Projector, Sound system, Video conferencing, Screens/TVs, Microphones
Catering: In-house catering, External catering allowed, Halal options, Vegetarian options, Kitchen available, Bar/drinks
Infrastructure: Parking, Generator/backup power, Air conditioning, Security, On-site staff
Outdoor: Garden/outdoor space, Rooftop, Pool area, Terrace, Courtyard
Payment: Mobile money (M-Pesa), Card payment, Bank transfer, Invoice
```

**Acceptance criteria:**
- [ ] All models created with correct column types, constraints, and indexes
- [ ] Migration runs successfully on clean DB and on existing DB with venue data
- [ ] Existing venue data preserved (new columns nullable or with defaults)
- [ ] Seed amenities inserted

---

## Task B2: Pydantic Schemas

**Files to create/modify:**

- `app/schemas/venue.py` — EXTEND with new fields
- `app/schemas/venue_space.py` — NEW
- `app/schemas/venue_photo.py` — NEW
- `app/schemas/amenity.py` — NEW
- `app/schemas/venue_verification.py` — NEW

**What to do:**

1. Extend existing venue schemas (VenueBase, VenueCreate, VenueUpdate, Venue) with new fields
2. Create schemas for all new entities following the Base/Create/Update/Response pattern
3. Create directory-specific response schemas:
   - `VenueDirectoryItem` — lightweight venue card (for listing page)
   - `VenueDirectoryDetail` — full venue profile (for detail page)
   - `VenueDirectoryResult` — paginated result with venues + pagination metadata
4. All response schemas must use `from_attributes = True`

**Acceptance criteria:**
- [ ] All request/response shapes match API contract exactly
- [ ] Validation rules: slug format, country code format, lat/lng ranges, max 10 photos enforcement
- [ ] Enum validators for VenueStatus, LayoutOption, RateType, PhotoCategory

---

## Task B3: CRUD Layer

**Files to create/modify:**

- `app/crud/crud_venue.py` — EXTEND existing
- `app/crud/crud_venue_space.py` — NEW
- `app/crud/crud_venue_photo.py` — NEW
- `app/crud/crud_amenity.py` — NEW
- `app/crud/crud_venue_verification.py` — NEW

**What to do:**

1. Extend venue CRUD with:
   - `get_by_slug(slug)` — for public detail page
   - `search_directory(filters)` — the main directory search with all filters, pagination, geo-search
   - `get_countries_with_venues()` — distinct countries with counts
   - `get_cities_with_venues(country?)` — distinct cities with counts
   - `submit_for_review(venue_id)` — status transition
   - `approve(venue_id)` / `reject(venue_id, reason)` / `suspend(venue_id, reason)` — admin actions
   - Auto-generate `slug` from `name` on create (handle duplicates with suffix)

2. Implement geo-search:
   - If PostGIS available: use `ST_DWithin` / `ST_Distance`
   - Fallback: Haversine formula in SQL: `acos(sin(radians(lat1)) * sin(radians(lat2)) + cos(radians(lat1)) * cos(radians(lat2)) * cos(radians(lng2 - lng1))) * 6371`
   - Index: create index on `(latitude, longitude)` for venues where `status = 'approved'`

3. Implement text search:
   - Use PostgreSQL `ILIKE` for name/city/address search
   - Consider `to_tsvector`/`to_tsquery` for full-text if performance becomes an issue

4. Create CRUD for all new entities following existing patterns (see `app/crud/base.py`)

**Acceptance criteria:**
- [ ] Directory search returns correct results for all filter combinations
- [ ] Geo-search returns venues within specified radius
- [ ] Slug generation handles duplicates (e.g., "kicc" → "kicc-2")
- [ ] Status transitions enforce valid state machine (draft → pending_review → approved/rejected)
- [ ] Pagination works correctly (offset-based)

---

## Task B4: REST API Endpoints — Public Directory

**Files to create:**

- `app/api/v1/endpoints/venue_directory.py` — NEW

**What to do:**

1. Implement all endpoints from API contract section 2.1:
   - `GET /api/v1/venues/directory` — search with all query params
   - `GET /api/v1/venues/directory/{slug}` — full venue detail
   - `GET /api/v1/venues/amenities` — amenity categories list
   - `GET /api/v1/venues/countries` — countries with venue counts
   - `GET /api/v1/venues/cities` — cities with venue counts

2. These endpoints have NO auth requirement — they are public

3. Register routes in `app/api/v1/api.py` router

4. Add response caching headers (Cache-Control) for amenities/countries/cities endpoints

**Acceptance criteria:**
- [ ] All endpoints return data matching API contract response shapes exactly
- [ ] No auth required for any public endpoint
- [ ] Directory search handles all filter combinations including geo-search
- [ ] 404 for non-existent slug

---

## Task B5: REST API Endpoints — Venue Owner CRUD

**Files to modify:**

- `app/api/v1/endpoints/venues.py` — EXTEND existing

**What to do:**

1. Extend existing venue CRUD endpoints to handle new fields (description, city, country, etc.)
2. Add new endpoint: `POST /organizations/{orgId}/venues/{venueId}/submit` — submit for review
3. Update GET to return nested spaces, photos, amenities for the owner view
4. Keep existing auth pattern: `current_user.org_id != orgId` check

**Acceptance criteria:**
- [ ] Existing venue CRUD still works (backwards compatible)
- [ ] New fields accepted on create/update
- [ ] Submit endpoint transitions status correctly
- [ ] Cannot submit if venue has no spaces (return 422)

---

## Task B6: REST API Endpoints — Spaces & Pricing

**Files to create:**

- `app/api/v1/endpoints/venue_spaces.py` — NEW

**What to do:**

1. Implement all endpoints from API contract sections 2.3 and 2.4:
   - `POST/GET/PATCH/DELETE` for spaces
   - `PUT` for pricing (idempotent replace)

2. Auth: same org ownership check pattern
3. Validate: venue must belong to org, space must belong to venue

**Acceptance criteria:**
- [ ] Full CRUD for spaces
- [ ] Pricing replacement is idempotent (delete all, insert new)
- [ ] Cascading: deleting a space deletes its pricing and unlinks photos

---

## Task B7: REST API Endpoints — Photos

**Files to create:**

- `app/api/v1/endpoints/venue_photos.py` — NEW

**What to do:**

1. Implement all endpoints from API contract section 2.5:
   - Two-step presigned upload (request + complete)
   - PATCH photo metadata
   - DELETE photo (also delete from S3)
   - PATCH reorder

2. Use existing `app/core/s3.py` utilities — call `generate_presigned_post()` with:
   - S3 key pattern: `venue-images/{venueId}/{sanitized_filename}`
   - Max size: 10MB
   - Content types: `image/jpeg`, `image/png`, `image/webp`

3. Enforce max 10 photos per venue (return 409 if exceeded)
4. When setting `is_cover: true`, unset any existing cover photo
5. On delete, call S3 delete object to clean up

**Acceptance criteria:**
- [ ] Presigned URL generation works for all allowed content types
- [ ] Photo record created on upload-complete
- [ ] Max 10 photo limit enforced
- [ ] Cover photo toggle works (only one cover at a time)
- [ ] S3 cleanup on photo deletion
- [ ] Reorder updates sort_order correctly

---

## Task B8: REST API Endpoints — Amenities

**Files to create:**

- `app/api/v1/endpoints/venue_amenities.py` — NEW

**What to do:**

1. Implement idempotent amenity set: `PUT /organizations/{orgId}/venues/{venueId}/amenities`
   - Delete all existing VenueAmenity rows for this venue
   - Insert new rows from request
   - Return resolved amenity names (joined with Amenity table)

2. Validate amenity_ids exist in the Amenity table

**Acceptance criteria:**
- [ ] Idempotent set works (repeated calls produce same result)
- [ ] Invalid amenity_id returns 400
- [ ] Response includes resolved amenity names and categories

---

## Task B9: REST API Endpoints — Verification & Admin

**Files to create:**

- `app/api/v1/endpoints/venue_verification.py` — NEW
- `app/api/v1/endpoints/venue_admin.py` — NEW

**What to do:**

1. Verification document upload (same two-step pattern as photos):
   - S3 key pattern: `venue-verification/{venueId}/{filename}`
   - Max size: 20MB
   - Allowed types: `application/pdf`, `image/jpeg`, `image/png`

2. Admin endpoints (require admin role check):
   - `GET /admin/venues` — list with filters
   - `POST /admin/venues/{venueId}/approve`
   - `POST /admin/venues/{venueId}/reject`
   - `POST /admin/venues/{venueId}/suspend`
   - `POST /admin/venues/{venueId}/request-documents`
   - CRUD for amenity categories and amenities

3. Domain match check: on venue submit, compare venue owner's email domain to venue website domain. Set `domain_match = True` if they match.

**Acceptance criteria:**
- [ ] Admin-only endpoints reject non-admin users with 403
- [ ] Status transitions enforce valid state machine
- [ ] Approval sets `verified = True` and `approved_at`
- [ ] Rejection stores reason and allows resubmission
- [ ] Domain match detection works correctly

---

## Task B10: GraphQL Schema Extensions

**Files to modify:**

- `app/graphql/types.py` — extend VenueType, add all new types
- `app/graphql/queries.py` — add directory queries
- `app/graphql/mutations.py` — extend venue mutations, add new mutations

**What to do:**

1. Extend `VenueType` with all new fields from API contract section 3.1
2. Add new types: `VenueSpaceType`, `VenuePhotoType`, `VenueAmenityType`, etc.
3. Add nested resolvers on `VenueType` for spaces, photos, amenities (use DataLoaders to avoid N+1)
4. Add `listedBy` resolver on `VenueType`: resolve `organization_id` → org name via HTTP call to user-and-org-service (`GET /organizations/{orgId}`) or via Apollo Federation entity reference. For admin context, also resolve owner email. Cache org lookups in DataLoader to avoid N+1.
5. Add all queries from API contract section 3.2
6. Add all mutations from API contract section 3.3
7. Add new input types

**Acceptance criteria:**
- [ ] All GraphQL types match API contract section 3
- [ ] Public queries work without auth
- [ ] DataLoaders prevent N+1 queries for nested data
- [ ] Federation still works (existing EventType.venue resolver unbroken)

---

## Task B11: Slug Generation Utility

**Files to create:**

- `app/utils/slug.py` — NEW

**What to do:**

1. Create `generate_slug(name: str, db: Session) -> str`:
   - Convert to lowercase
   - Replace spaces/special chars with hyphens
   - Remove non-alphanumeric chars (except hyphens)
   - Collapse multiple hyphens
   - Check for uniqueness in DB
   - If duplicate, append `-2`, `-3`, etc.
   - Handle unicode (transliterate accented chars)

**Acceptance criteria:**
- [ ] "Kenyatta International Convention Centre" → "kenyatta-international-convention-centre"
- [ ] Duplicate handling: "kicc" → "kicc", "kicc" → "kicc-2"
- [ ] Unicode: "Café des Arts" → "cafe-des-arts"
- [ ] No trailing/leading hyphens

---

## Execution Order

The tasks have dependencies. Recommended order:

```
B1 (Models & Migration)
  ↓
B2 (Schemas)        B11 (Slug utility)
  ↓                   ↓
B3 (CRUD layer) ←────┘
  ↓
B4 (Public API)     B5 (Owner CRUD)     B6 (Spaces)     B7 (Photos)     B8 (Amenities)
  ↓                   ↓                   ↓               ↓               ↓
  └───────────────────┴───────────────────┴───────────────┘               |
                                          ↓                               |
                                    B9 (Verification & Admin) ←──────────┘
                                          ↓
                                    B10 (GraphQL)
```

B4 through B8 can be built in parallel once B1-B3 are done.
