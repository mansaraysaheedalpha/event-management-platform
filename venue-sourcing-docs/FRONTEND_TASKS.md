# Venue Sourcing — Frontend Implementation Tasks

**App:** `globalconnect` (Next.js 15 / React 19 / TypeScript)
**Reference:** [API_CONTRACT.md](API_CONTRACT.md) — build exactly to this contract
**Reference:** [../venue-mockup.html](../venue-mockup.html) — UI reference mockup
**Reference:** [VENUE_SOURCING_GOLDEN_DIRECTORY_SPEC.md](../VENUE_SOURCING_GOLDEN_DIRECTORY_SPEC.md) — feature spec

---

## Conventions (From Existing Codebase)

| Convention | Rule |
|---|---|
| Styling | Tailwind CSS + Radix UI primitives + shadcn/ui components |
| State | Apollo Client (server data), Zustand (global UI state), React Hook Form (forms) |
| GraphQL | Operations in `src/graphql/*.graphql.ts`, codegen types in `src/gql/` |
| Routing | Next.js App Router, route groups: `(public)`, `(platform)`, `(admin)`, `(attendee)` |
| Components | Shared in `src/components/`, feature-scoped in page `_components/` dirs |
| File uploads | `react-dropzone` + presigned S3 POST (two-step: request URL → upload → confirm) |

---

## Task F1: GraphQL Operations & Codegen

**Files to create/modify:**

- `src/graphql/venue-directory.graphql.ts` — NEW (public directory queries)
- `src/graphql/venue-management.graphql.ts` — NEW (owner mutations)
- `src/graphql/venue-admin.graphql.ts` — NEW (admin queries/mutations)
- `src/graphql/venues.graphql.ts` — EXTEND existing with new fields
- Run codegen to generate types

**What to do:**

1. Define all GraphQL operations matching the API contract section 3:

**venue-directory.graphql.ts:**
```graphql
# VENUE_DIRECTORY_QUERY — for /venues page
query VenueDirectory($q: String, $country: String, $city: String, ...) {
  venueDirectory(...) { venues { ... } totalCount page pageSize totalPages }
}

# VENUE_BY_SLUG_QUERY — for /venues/[slug] page
query VenueBySlug($slug: String!) {
  venueBySlug(slug: $slug) { id slug name description ... spaces { ... } photos { ... } amenities { ... } }
}

# VENUE_AMENITY_CATEGORIES_QUERY — for filter sidebar
query VenueAmenityCategories { venueAmenityCategories { id name icon amenities { id name } } }

# VENUE_COUNTRIES_QUERY — for country dropdown
query VenueCountries { venueCountries { code name venueCount } }

# VENUE_CITIES_QUERY — for city dropdown
query VenueCities($country: String) { venueCities(country: $country) { name country venueCount } }
```

**venue-management.graphql.ts:**
```graphql
# All owner mutations: createVenue, updateVenue, submitVenueForReview,
# createVenueSpace, updateVenueSpace, deleteVenueSpace,
# setSpacePricing, setVenueAmenities,
# updateVenuePhoto, deleteVenuePhoto, reorderVenuePhotos
```

**venue-admin.graphql.ts:**
```graphql
# ADMIN_VENUE_QUEUE_QUERY
# APPROVE_VENUE_MUTATION, REJECT_VENUE_MUTATION, SUSPEND_VENUE_MUTATION
```

2. Run `npm run codegen` (or equivalent) to generate TypeScript types
3. Update existing `venues.graphql.ts` operations to include new fields

**Acceptance criteria:**
- [ ] All operations defined and type-safe after codegen
- [ ] Fragment reuse where sensible (VenueCardFragment, VenueDetailFragment)
- [ ] Existing venue operations still work (backwards compatible)

---

## Task F2: Public Venue Directory Page — `/venues`

**Files to create:**

- `src/app/(public)/venues/page.tsx` — main directory page
- `src/app/(public)/venues/_components/venue-search-hero.tsx`
- `src/app/(public)/venues/_components/venue-filter-sidebar.tsx`
- `src/app/(public)/venues/_components/venue-card.tsx`
- `src/app/(public)/venues/_components/venue-grid.tsx`
- `src/app/(public)/venues/_components/venue-map-view.tsx`
- `src/app/(public)/venues/_components/active-filters.tsx`
- `src/app/(public)/venues/_components/venue-pagination.tsx`

**What to do:**

1. **Search Hero Section** (top of page):
   - Text search input (debounced, 300ms)
   - Country dropdown (populated from `VenueCountries` query)
   - City dropdown (populated from `VenueCities` query, filtered by selected country)
   - "Search Venues" button
   - Quick stats: total venues, countries, cities

2. **Filter Sidebar** (left):
   - Minimum capacity input
   - Price range (min/max) inputs
   - Amenity checkboxes grouped by category (from `VenueAmenityCategories` query)
   - "Apply Filters" button
   - "Clear All" link

3. **Results Area** (right):
   - View toggle: Grid / List / Map
   - Sort dropdown: Recommended, Price Low→High, Price High→Low, Capacity, Newest
   - Active filter chips (removable)
   - Venue card grid (responsive: 1 col mobile, 2 col tablet, 3 col desktop)
   - Pagination component

4. **Venue Card**:
   - Cover photo (gradient placeholder if no photo)
   - Verified badge (green checkmark) or "New" badge
   - Venue name, location (city, country)
   - Amenity highlight chips (top 4)
   - Capacity, space count, starting price
   - Save/heart button

5. **Map View** (toggle):
   - Map component with venue pins (use Leaflet + OpenStreetMap for free tier)
   - Radius search: location input + radius dropdown
   - Pin hover shows venue name + cover photo
   - Pin click navigates to venue detail

6. **URL State**: Store all filter state in URL search params so links are shareable
   - Example: `/venues?country=KE&city=Nairobi&amenities=vam_wifi01,vam_gen01&min_capacity=50`

**Acceptance criteria:**
- [ ] Full search and filter functionality working against GraphQL
- [ ] URL-driven filter state (shareable links, back button works)
- [ ] Responsive layout (mobile, tablet, desktop)
- [ ] Map view with clickable pins
- [ ] Loading states and empty states
- [ ] Pagination working correctly

---

## Task F3: Venue Detail Page — `/venues/[slug]`

**Files to create:**

- `src/app/(public)/venues/[slug]/page.tsx` — venue detail page
- `src/app/(public)/venues/[slug]/_components/venue-photo-gallery.tsx`
- `src/app/(public)/venues/[slug]/_components/venue-amenities-grid.tsx`
- `src/app/(public)/venues/[slug]/_components/venue-spaces-list.tsx`
- `src/app/(public)/venues/[slug]/_components/venue-contact-card.tsx`
- `src/app/(public)/venues/[slug]/_components/venue-location-map.tsx`

**What to do:**

1. **Photo Gallery** (top):
   - Grid layout: large cover photo left, 4 smaller photos right (like Airbnb)
   - "+N more" overlay on last photo if > 5 photos
   - Category filter tabs below gallery (All, Exterior, Interior, etc.)
   - Click to open fullscreen lightbox modal
   - Graceful handling when venue has 0-1 photos

2. **Header**: Venue name, verified badge, location, save + share buttons

3. **About Section**: Description text

4. **Amenities Grid**: Two-column grid with green checkmarks, organized by category

5. **Spaces & Rooms List**:
   - Each space as an expandable card
   - Shows: name, floor, capacity, layout option chips, pricing (per day + per hour)
   - "Largest space" badge on the biggest one
   - "View all N spaces" button if > 3 spaces

6. **Location Map**: Embedded map showing venue location pin

7. **Contact Sidebar** (sticky right):
   - Phone, email, WhatsApp (with WhatsApp deep link: `https://wa.me/{number}`), website
   - "Request a Quote" button (placeholder for RFP system)
   - "Link to My Event" button (links venue to user's event)
   - Accepted payment methods
   - "Listed by" section with org name and member since date (from `listedBy` field on VenueType)

8. **Breadcrumb**: Venues → {Country} → {Venue Name}

**Acceptance criteria:**
- [ ] Fetches venue by slug via GraphQL
- [ ] Photo gallery works with 0 to 10 photos
- [ ] Category tab filtering for photos
- [ ] WhatsApp link opens WhatsApp with venue number
- [ ] Responsive: sidebar moves below content on mobile
- [ ] SEO: page title, meta description from venue data
- [ ] 404 page if slug not found

---

## Task F4: Venue Owner Dashboard — Extend `/platform/venues`

**Files to modify/create:**

- `src/app/(platform)/venues/page.tsx` — EXTEND existing page
- `src/app/(platform)/venues/_components/venue-listing-card.tsx` — NEW
- `src/app/(platform)/venues/_components/venue-stats.tsx` — NEW
- `src/app/(platform)/venues/_components/completeness-indicator.tsx` — NEW

**What to do:**

1. Extend the existing venue management page to show richer listing cards:
   - Thumbnail, name, status badge (Draft/Pending/Approved/Rejected/Suspended), verified badge
   - Location, space count, capacity summary
   - Completeness indicator bar (percentage based on filled fields)
   - Rejection reason banner (if status = rejected)
   - Pending review info banner (if status = pending_review)
   - Quick actions: Edit, View Public (if approved), Continue Editing (if draft)

2. Stats row at top: Total Listings, Approved, Pending, Drafts

3. "Add New Venue" button → opens create modal or navigates to create page

4. Completeness calculation (frontend):
   - Has name (+10%), has description (+10%), has address/city/country (+10%)
   - Has at least 1 photo (+15%), has cover photo (+5%)
   - Has at least 1 space (+15%), spaces have pricing (+10%)
   - Has at least 3 amenities (+10%), has contact info (+10%), has verification docs (+5%)

**Acceptance criteria:**
- [ ] Existing venue management functionality unbroken
- [ ] Status badges display correctly for all 5 states
- [ ] Completeness indicator calculates and displays accurately
- [ ] Rejection reason shown clearly for rejected venues

---

## Task F5: Venue Create/Edit Form

**Files to create:**

- `src/app/(platform)/venues/[id]/edit/page.tsx` — NEW
- `src/app/(platform)/venues/[id]/edit/_components/venue-basic-info-form.tsx`
- `src/app/(platform)/venues/[id]/edit/_components/venue-photo-uploader.tsx`
- `src/app/(platform)/venues/[id]/edit/_components/venue-spaces-manager.tsx`
- `src/app/(platform)/venues/[id]/edit/_components/venue-amenities-selector.tsx`
- `src/app/(platform)/venues/[id]/edit/_components/venue-verification-uploader.tsx`
- `src/app/(platform)/venues/[id]/edit/_components/venue-edit-sidebar.tsx`

**What to do:**

1. **Tabbed/Section edit form** with sections:
   - Basic Info (name, description, address, city, country, coordinates, contact)
   - Photos (upload, categorize, reorder, set cover)
   - Spaces & Pricing (add/edit/remove spaces, set pricing per space)
   - Amenities (checkbox grid grouped by category)
   - Verification (document upload, status display)

2. **Basic Info Form** (React Hook Form):
   - Name, description (textarea), address, city, country (dropdown)
   - Coordinates: either manual lat/lng input or "Use map to set location" picker
   - Website, phone, email, WhatsApp
   - Auto-save or explicit "Save" button

3. **Photo Uploader**:
   - `react-dropzone` drag-and-drop area
   - Two-step upload: request presigned URL (REST) → upload to S3 → confirm (REST)
   - Show upload progress
   - After upload: display photo grid with category dropdown, caption input, cover toggle
   - Drag-to-reorder (use `@dnd-kit/core` or similar)
   - Delete button with confirmation
   - "10 photo limit" indicator

4. **Spaces Manager**:
   - List of spaces with inline edit
   - "Add Space" button → inline form or modal
   - Per-space: name, description, capacity, floor, layout checkboxes
   - Per-space pricing: add rate rows (rate type dropdown, amount input, currency dropdown)
   - Delete space with confirmation

5. **Amenities Selector**:
   - Fetch amenity categories via `VenueAmenityCategories` query
   - Display as checkbox groups (like the filter sidebar but for editing)
   - Some amenities have metadata inputs (e.g., Wi-Fi speed tier dropdown)
   - Save via `setVenueAmenities` mutation

6. **Verification Uploader**:
   - Document type selector (Business Registration, Utility Bill, Tax Certificate, Other)
   - File upload (same two-step pattern, but for PDFs + images)
   - Display uploaded docs with status (Uploaded, Reviewed, Accepted, Rejected)
   - Admin notes visible if rejected

7. **Sidebar** (sticky):
   - Completeness indicator
   - Venue status badge
   - "Submit for Review" button (enabled only when venue meets minimum requirements)
   - "Preview Listing" link
   - Tips: "Add photos to improve your listing"

**Acceptance criteria:**
- [ ] All form fields save correctly via GraphQL mutations (or REST for uploads)
- [ ] Photo upload works end-to-end (presigned URL → S3 → confirm)
- [ ] Photo reorder and cover selection work
- [ ] Spaces with pricing CRUD works
- [ ] Amenity selection saves correctly
- [ ] Verification document upload works
- [ ] Submit for review transitions status correctly
- [ ] Form validates required fields before submit
- [ ] Loading/saving states throughout

---

## Task F6: Admin Venue Review Page — `/admin/venues`

**Files to create:**

- `src/app/(admin)/admin/venues/page.tsx` — NEW (review queue)
- `src/app/(admin)/admin/venues/[id]/page.tsx` — NEW (review detail)
- `src/app/(admin)/admin/venues/_components/venue-review-table.tsx`
- `src/app/(admin)/admin/venues/_components/venue-review-actions.tsx`
- `src/app/(admin)/admin/venues/_components/amenity-manager.tsx`
- `src/app/(admin)/admin/amenities/page.tsx` — NEW

**What to do:**

1. **Review Queue Table**:
   - Columns: Venue (name + thumb), Location, Submitted By (name + email, from `listedBy` resolver), Documents (status chips), Priority (fast-track badge if domain match), Submitted date, Actions
   - Filters: status dropdown, domain match toggle
   - Sort by submission date (oldest first by default)
   - Pagination

2. **Review Detail Page** (`/admin/venues/[id]`):
   - Full venue preview (same layout as public detail page)
   - Verification documents panel: view/download each doc
   - Owner information: name, email, org details
   - Domain match indicator
   - Action buttons: Approve, Reject (with reason textarea), Suspend, Request Documents (with message textarea)
   - Review history/notes section

3. **Amenity Manager** (`/admin/amenities`):
   - List all amenity categories with nested amenities
   - Add/edit/delete categories
   - Add/edit/delete amenities within categories
   - Reorder categories and amenities
   - Show usage count (how many venues use each amenity)

**Acceptance criteria:**
- [ ] Review queue loads and filters correctly
- [ ] Approve/reject/suspend actions work and update the table
- [ ] Rejection requires a reason
- [ ] Verification documents viewable/downloadable
- [ ] Fast-track (domain match) visually indicated
- [ ] Amenity CRUD works for admin

---

## Task F7: Map Integration (Leaflet + OpenStreetMap)

**Files to create:**

- `src/components/venue-map.tsx` — reusable map component

**What to do:**

1. Install: `npm install leaflet react-leaflet @types/leaflet`

2. Create a reusable `VenueMap` component that supports:
   - **Display mode**: Show a single venue pin (for detail page)
   - **Search mode**: Show multiple venue pins with hover cards (for directory)
   - **Picker mode**: Click-to-place pin and return lat/lng (for venue edit form)

3. Use OpenStreetMap tiles (free, no API key needed):
   - `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`

4. Venue pin popup: venue name, cover photo thumbnail, capacity, "View" link

5. Handle: Next.js SSR (Leaflet needs `dynamic(() => import(...), { ssr: false })`)

**Acceptance criteria:**
- [ ] Map renders without SSR errors
- [ ] Display mode shows single pin correctly
- [ ] Search mode shows multiple pins with hover cards
- [ ] Picker mode returns lat/lng on click
- [ ] Responsive (full-width on mobile)

---

## Task F8: Shared Components

**Files to create:**

- `src/components/venue/verified-badge.tsx`
- `src/components/venue/venue-status-badge.tsx`
- `src/components/venue/amenity-chip.tsx`
- `src/components/venue/price-display.tsx`
- `src/components/venue/completeness-bar.tsx`
- `src/components/venue/photo-lightbox.tsx`

**What to do:**

1. **VerifiedBadge**: Green checkmark + "Verified" text, small variant for cards
2. **VenueStatusBadge**: Colored badge for draft/pending/approved/rejected/suspended
3. **AmenityChip**: Small pill showing amenity name, optional icon
4. **PriceDisplay**: Formats price with currency (KES 150,000/day), handles multiple rate types
5. **CompletenessBar**: Progress bar with percentage and text hint
6. **PhotoLightbox**: Fullscreen modal gallery with navigation arrows, category filter

**Acceptance criteria:**
- [ ] All components reusable and typed with proper props
- [ ] Price display handles all currencies (KES, NGN, USD, ZAR, GBP, etc.)
- [ ] Lightbox supports keyboard navigation (arrows, escape)

---

## Execution Order

```
F1 (GraphQL Operations + Codegen)
  ↓
F8 (Shared Components)     F7 (Map Component)
  ↓                          ↓
F2 (Directory Page) ←───────┘
  ↓
F3 (Detail Page)
  ↓
F4 (Owner Dashboard)
  ↓
F5 (Create/Edit Form)
  ↓
F6 (Admin Review)
```

F1 must be first. F7 and F8 can be built in parallel. F2-F6 are sequential because each builds on patterns from the previous.

**Note for frontend dev:** You can start building F2-F6 with mock data while waiting for the backend. The API contract defines the exact shapes. Use Apollo Client's `MockedProvider` or a local mock server for development.
