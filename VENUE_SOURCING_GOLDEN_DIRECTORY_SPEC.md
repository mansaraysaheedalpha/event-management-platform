# Venue Sourcing — Golden Directory Specification

**Phase 1, Section 1: Detailed Listings + Smart Filter**
**Date:** February 2026
**Status:** Pending Boss Approval

---

## 1. Overview

The Golden Directory is a rich, searchable public database of event venues. It transforms our existing basic venue system (name + address only) into a comprehensive venue marketplace where venue owners manage their own listings and event organizers discover, compare, and ultimately book venues.

This is the foundation layer. Everything that follows — the RFP system, waitlist/queue, AI concierge, and autonomous booking — depends on having high-quality, detailed venue data in place first.

---

## 2. Architecture

### Hybrid Model

We use a two-tier approach:

- **Public Directory:** A shared database of venues visible to all users. Any organizer can browse and link a venue to their event. Venue owners manage their own listings.
- **Org-Private Venues:** Organizers can still create private venues (e.g., their company's own conference room) that only their organization sees.

This preserves our existing functionality while building toward the marketplace vision.

### Venue Owner Accounts

Venue owners use the **same authentication system** as organizers. They register normally, then create a "Venue Organization" — similar to an event organization but designated for venue management. This reuses our existing auth, roles, and permissions infrastructure.

---

## 3. Venue Profile — What Every Listing Contains

### 3.1 Basic Information

| Field            | Type     | Notes                                              |
| ---------------- | -------- | -------------------------------------------------- |
| Name             | Text     | Required                                           |
| Description      | Text     | Rich description of the venue                      |
| Address          | Text     | Full street address                                |
| City             | Text     | For filtering                                      |
| Country          | Text     | For filtering                                      |
| Latitude         | Decimal  | For map display and radius search                  |
| Longitude        | Decimal  | For map display and radius search                  |
| Website          | URL      | Optional                                           |
| Phone            | Text     | Optional                                           |
| Email            | Text     | Optional                                           |
| WhatsApp Number  | Text     | Important for African markets where WhatsApp is the primary business communication channel |

### 3.2 Photos (Flexible Gallery)

- Up to **10 photos** per venue
- First uploaded photo is auto-designated as **cover image** (owner can change it)
- Photos can **optionally** be tagged with a category:
  - Exterior
  - Interior / Lobby
  - Event Rooms / Spaces
  - Amenities (pool, garden, parking, etc.)
  - Catering / Dining
  - General (default if no category selected)
- Categories are **recommended, not enforced** — the UI nudges venue owners with:
  - A completeness indicator: "Your listing is 70% complete — adding room photos helps organizers decide faster"
  - A category suggestion during upload: "What does this photo show?" (dropdown defaulting to "General")
- If photos have categories, the venue profile shows organized tabs; otherwise, a flat gallery
- Uses our existing S3 upload infrastructure (presigned POST)

### 3.3 Amenities — The "Smart Filter" Toggles

Amenities are organized into **predefined categories** with structured options. This ensures consistent filtering across all venues. Admins can add new amenities over time.

| Category        | Example Amenities                                                    |
| --------------- | -------------------------------------------------------------------- |
| **Accessibility** | Wheelchair access, Elevator, Accessible restrooms, Braille signage |
| **Technology**    | Wi-Fi (with speed tier), Projector, Sound system, Video conferencing, Screens/TVs, Microphones |
| **Catering**      | In-house catering, External catering allowed, Halal options, Vegetarian options, Kitchen available, Bar/drinks |
| **Infrastructure**| Parking (+ capacity), Generator/backup power, Air conditioning, Security, On-site staff |
| **Outdoor**       | Garden/outdoor space, Rooftop, Pool area, Terrace, Courtyard        |
| **Payment**       | Mobile money (M-Pesa, etc.), Card payment, Bank transfer, Invoice   |

### 3.4 Spaces / Rooms (Sub-entities)

Each venue can have **multiple bookable spaces**, each with:

| Field           | Type       | Notes                                               |
| --------------- | ---------- | --------------------------------------------------- |
| Name            | Text       | e.g., "Ballroom A", "Boardroom 3"                   |
| Capacity        | Integer    | Maximum number of people                             |
| Layout Options  | List       | Theater, Classroom, Banquet, U-shape, Boardroom, Cocktail |
| Photos          | Gallery    | Per-space photos (subset of main gallery or separate)|
| Floor/Level     | Text       | Optional — e.g., "2nd Floor", "Ground Floor"        |

### 3.5 Pricing

Structured pricing **per space**:

| Field        | Type     | Notes                                |
| ------------ | -------- | ------------------------------------ |
| Rate Type    | Enum     | Hourly, Half-Day, Full-Day           |
| Amount       | Decimal  | Price in the specified currency       |
| Currency     | String   | e.g., KES, NGN, USD, ZAR, GBP       |

Multiple rate types can exist per space (e.g., both hourly and full-day rates).

---

## 4. Search & Discovery

### 4.1 Text-Based Search

- Search by venue name (fuzzy/partial match)
- Filter by country and city (dropdown selectors)
- Free-text address search

### 4.2 Geo-Search with Map

- All venues store latitude/longitude coordinates
- Users can view venues on an interactive map
- Radius-based search: "Show venues within 10km of [location]"
- Map pins with venue name and cover photo preview on hover

### 4.3 Smart Filters (Toggle-Based)

- Users toggle amenity requirements: "Must have wheelchair access", "Must have Wi-Fi", "Must have parking"
- Filters work as AND conditions (venue must have ALL selected amenities)
- Capacity filter: "Minimum capacity of 50 people"
- Price range filter

---

## 5. Directory Pages (Frontend)

### 5.1 Public Pages (Visible to Everyone)

| Route                | Description                                         |
| -------------------- | --------------------------------------------------- |
| `/venues`            | Public directory — search, filter, browse all verified venues |
| `/venues/[slug]`     | Individual venue profile page with full details, photos, spaces, map |

### 5.2 Venue Owner Dashboard

| Route                         | Description                                        |
| ----------------------------- | -------------------------------------------------- |
| `/platform/venues`            | Venue owner's listing management dashboard          |
| `/platform/venues/[id]/edit`  | Edit venue details, photos, spaces, pricing         |

### 5.3 Admin Panel

| Route                        | Description                                         |
| ---------------------------- | --------------------------------------------------- |
| `/admin/venues`              | Review pending venue submissions                     |
| `/admin/venues/[id]`         | Verify/approve/reject venue listings                 |
| `/admin/amenities`           | Manage predefined amenity categories and options     |

---

## 6. Verification & Trust

### Primary: Document Upload + Admin Review

1. Venue owner submits their listing with required documents (business registration certificate, utility bill, or similar proof)
2. Admin team reviews the submission
3. Admin approves, requests changes, or rejects
4. Approved venues get a "Verified" badge on their listing

### Supplementary: Email Domain Fast-Track

- If a venue owner registers with an email matching the venue's domain (e.g., `manager@hiltonnairobi.com`), their submission is **priority-queued** for review
- This does not auto-approve — it reduces documentation requirements and elevates priority
- Small venues using Gmail/Yahoo go through the standard review process

### Venue States

| State         | Visibility        | Description                              |
| ------------- | ----------------- | ---------------------------------------- |
| Draft         | Owner only        | Venue is being set up, not yet submitted |
| Pending Review| Owner + Admins    | Submitted for verification               |
| Approved      | Public            | Verified and visible in directory         |
| Rejected      | Owner only        | Rejected with reason, can resubmit       |
| Suspended     | None              | Temporarily removed by admin             |

---

## 7. Who Populates the Directory

Two channels work in parallel:

1. **Venue Owners (Self-Service):** Register on the platform, create a venue organization, add their listings, submit for verification
2. **Admin Team (Curation):** Research and add high-quality venues directly, mark them as verified. This seeds the directory with initial content before venue owners start joining

---

## 8. Technical Approach (High-Level)

- **Backend:** Extends the existing `event-lifecycle-service` (Python/FastAPI/SQLAlchemy) as an **isolated module** with clear domain boundaries. New models (venue spaces, amenities, photos, verification) are organized under a venue-sourcing namespace within the service. This avoids the distributed systems overhead of a separate service while keeping the code cleanly separated. If scale demands it later, extraction to a dedicated service is straightforward because module boundaries are already established.
- **API:** Both REST and GraphQL endpoints (following existing patterns).
- **File Uploads:** Uses existing S3 presigned POST pattern for venue photos.
- **Auth:** Extends existing JWT-based auth with a new "venue owner" role/organization type.
- **Frontend:** Next.js 15 pages with Apollo Client, Tailwind CSS, Radix UI components.
- **Map:** Interactive map component for geo-search (library TBD — likely Mapbox or Leaflet).
- **Search:** PostgreSQL full-text search + PostGIS for geo-queries (or application-level Haversine if PostGIS is not available).

> **Architectural note:** We evaluated creating a dedicated `venue-service` but decided against it for now. The existing `Event` model has a direct foreign key to `Venue` — splitting this across services would introduce cross-service data consistency challenges, added latency for every event query, and infrastructure cost (new database + deployment) without proportional benefit at current scale. The isolated module approach gives us clean code boundaries today and a clear extraction path if needed tomorrow.

---

## 9. What This Enables Next

Once the Golden Directory is live with rich venue data:

- **Phase 1, Section 2 (RFP System):** Organizers send standardized RFPs to multiple venues, compare responses side-by-side
- **Phase 1, Section 3 (Waitlist):** Users join waitlists for fully-booked dates
- **Phase 2 (AI Layer):** Natural language search, autonomous monitoring, AI negotiation — all powered by the structured venue data we build here

---

## 10. Open Questions for Discussion

1. Should we support multiple languages for venue descriptions (e.g., English + French + Swahili)?
2. Do we need venue operating hours at launch?
3. Should venue owners see analytics (profile views, search appearances) from day one?
4. What map provider should we use? (Mapbox, Google Maps, Leaflet + OpenStreetMap)
