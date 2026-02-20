# Venue Sourcing Feature - Issues & Bugs Report

**Generated**: 2026-02-20
**Total Issues Found**: 17
**Critical**: 7 | **High Priority**: 4 | **Medium Priority**: 6

---

## CRITICAL ISSUES (Breaks Functionality)

### Issue #1: Status Case Mismatch - Breaks ALL Status-Driven UI ⚠️ HIGHEST IMPACT

**Severity**: CRITICAL
**Impact**: Breaks all status-based UI logic across the entire venue feature

**Problem**:
- Backend returns: `"draft"`, `"pending_review"`, `"approved"`, `"rejected"`, `"suspended"` (lowercase)
- Frontend expects: `"DRAFT"`, `"PENDING_REVIEW"`, `"APPROVED"`, `"REJECTED"`, `"SUSPENDED"` (UPPERCASE)

**Affected Files**:
- `globalconnect/src/app/(platform)/my-venues/[venueId]/edit/_components/venue-edit-sidebar.tsx` (lines 38, 64, 91)
- `globalconnect/src/app/(platform)/my-venues/_components/venue-listing-card.tsx` (lines 68, 83, 110, 124)
- `globalconnect/src/app/(platform)/my-venues/_components/venue-stats.tsx` (lines 14-16)
- `globalconnect/src/app/(admin)/admin/venues/_components/venue-review-actions.tsx` (lines 91-94)
- `globalconnect/src/app/(admin)/admin/venues/page.tsx` (line 27)

**Broken Functionality**:
- ❌ Venue stats always show **0 for all counts** (Draft: 0, Pending: 0, Approved: 0)
- ❌ Status badges/banners never appear correctly
- ❌ Submit for Review button always disabled
- ❌ Admin action buttons incorrectly enabled/disabled
- ❌ "View Public" button never shows even for approved venues
- ❌ "Continue Editing" label never shows for drafts
- ❌ Rejection banner never shows
- ❌ "Under Review" banner never shows
- ❌ Admin default filter sends wrong value to backend

**Fix Strategy**: Normalize all status comparisons to lowercase using `.toLowerCase()` or update backend to return uppercase values

---

### Issue #2: My Venues Page Always Shows Empty State

**Severity**: CRITICAL
**Impact**: Main venue listing page shows "No venues yet" even when user has venues

**Problem**:
- File: `globalconnect/src/app/(platform)/my-venues/page.tsx:30`
- Type alias defines wrong cache key: `organizationVenues`
- GraphQL query operation returns: `organizationVenuesFull`
- Result: `data?.organizationVenues` is always `undefined`

**Code**:
```typescript
type VenuesQueryData = {
  organizationVenues: Venue[];  // ❌ WRONG - should be organizationVenuesFull
};
```

**Additional Impact**:
- Cache update after archive venue fails silently (writes to wrong key)

**Fix**: Change `organizationVenues` → `organizationVenuesFull` in type alias and cache.writeQuery

---

### Issue #3: Build Error - Missing Import 🔴 BLOCKS APP

**Severity**: CRITICAL
**Impact**: Build fails or runtime error when accessing create venue page

**Problem**:
- File: `globalconnect/src/app/(platform)/my-venues/new/page.tsx:17`
- Imports `COUNTRY_CODES` which doesn't exist in `venue.types.ts`
- Only `COUNTRY_NAMES` is exported

**Code**:
```typescript
import { COUNTRY_CODES, COUNTRY_NAMES } from "@/types/venue.types";
// ❌ COUNTRY_CODES does not exist
```

**Fix**: Remove `COUNTRY_CODES` from import statement (it's not used in the component)

---

### Issue #4: Waitlist Mutations - Parameter Name Mismatches (3 mutations)

**Severity**: CRITICAL
**Impact**: All waitlist join/cancel/respond operations fail with GraphQL schema errors

**Problems**:

| Mutation | Frontend Parameter | Backend Expects | Status |
|----------|-------------------|-----------------|--------|
| `joinVenueWaitlist` | `sourceRfpVenueId` | `rfpVenueId` | ❌ Schema error |
| `cancelWaitlistEntry` | `waitlistId` | `waitlistEntryId` | ❌ Schema error |
| `respondStillInterested` | `waitlistId` | `waitlistEntryId` | ❌ Schema error |

**Affected Files**:
- Frontend: `globalconnect/src/graphql/waitlist-mutations.ts`
- Backend: `event-lifecycle-service/app/graphql/venue_waitlist_mutations.py`

**Fix Options**:
1. Update backend parameter names to match frontend (recommended)
2. Update frontend queries to match backend

---

### Issue #5: convertWaitlistHold - Incompatible Return Types

**Severity**: CRITICAL
**Impact**: Converting waitlist holds crashes the UI

**Problem**:
- Frontend expects:
  ```graphql
  { waitlistEntry { id status convertedRfpId updatedAt }, newRfp { id title status } }
  ```
- Backend returns:
  ```python
  { success, newRfpId, waitlistEntryId, message }
  ```
- Completely different object shapes

**Affected Files**:
- Frontend: `globalconnect/src/graphql/waitlist-mutations.ts` (CONVERT_WAITLIST_HOLD)
- Backend: `event-lifecycle-service/app/graphql/venue_waitlist_types.py` (ConvertHoldResponse)

**Fix**: Align return types - either update backend to return nested objects or update frontend to use flat response

---

### Issue #6: Admin Queue - Missing Relations

**Severity**: CRITICAL
**Impact**: Admin venue review page shows empty data for critical fields

**Problem**:
- File: `event-lifecycle-service/app/graphql/venue_queries.py:355`
- `admin_venue_queue_query` doesn't use `joinedload` for relations
- Doesn't call `_venue_model_to_gql` with `include_relations=True` or `include_verification=True`

**Missing Data in Admin UI**:
- ❌ `listedBy` (organization info) - always null
- ❌ `verificationDocuments` - always empty array
- ❌ `spaces` - always empty array
- ❌ `spaceCount` - always 0
- ❌ `amenities` - always empty array

**Fix**: Add `joinedload` in `get_admin_venues()` CRUD and pass `include_relations=True, include_verification=True` to converter

---

### Issue #7: Venue Dashboard Edit Button - Wrong Route

**Severity**: CRITICAL
**Impact**: Edit button on venue dashboard navigates to 404

**Problem**:
- File: `globalconnect/src/app/(platform)/my-venues/[venueId]/page.tsx:82`
- Routes to: `/venues/${venue.id}/edit` (doesn't exist)
- Should route to: `/my-venues/${venue.id}/edit`

**Code**:
```typescript
router.push(`/venues/${venue.id}/edit`)  // ❌ Wrong
router.push(`/my-venues/${venue.id}/edit`)  // ✅ Correct
```

**Fix**: Update route path

---

## HIGH PRIORITY ISSUES (Data Always Wrong)

### Issue #8: Organization Venues Query - No Relations Loaded

**Severity**: HIGH
**Impact**: Venue listing cards show incomplete/empty data

**Problem**:
- File: `event-lifecycle-service/app/graphql/venue_queries.py:315`
- `organization_venues_query` doesn't use `joinedload` for relations
- Doesn't call `_venue_model_to_gql` with `include_relations=True`

**Missing Data in Listing Cards**:
- ❌ Photos - always empty (photo count shows 0)
- ❌ Spaces - always empty (space count shows 0)
- ❌ Amenities - always empty
- ❌ Min price - always null
- ❌ Completeness bar - always 0%
- ❌ Amenity highlights - always empty

**Fix**: Add `joinedload` or call `get_with_relations()` per venue and use `include_relations=True`

---

### Issue #9: availabilityStatus Always "not_set"

**Severity**: HIGH
**Impact**: Public venue cards never show actual availability status

**Problem**:
- `_venue_model_to_gql` function never maps `venue.availability_status` from ORM model
- `VenueFullType` has default `availabilityStatus: str = "not_set"`
- No code path assigns the actual value

**Affected Files**:
- `event-lifecycle-service/app/graphql/venue_queries.py` (_venue_model_to_gql function)
- Frontend: `VENUE_DETAIL_FRAGMENT` requests the field but always gets default

**Fix**: Add `availabilityStatus=venue.availability_status` to VenueFullType constructor

---

### Issue #10: Venue Directory Cards - Missing Fragment Fields

**Severity**: HIGH
**Impact**: Public directory grid shows incomplete venue cards

**Problem**:
- File: `globalconnect/src/graphql/venue-directory.graphql.ts`
- `VENUE_CARD_FRAGMENT` only includes: `id, slug, name, city, country, address, lat, lng, totalCapacity, verified`
- Missing fields that UI components use:
  - `coverPhotoUrl`
  - `spaceCount`
  - `minPrice { amount currency rateType }`
  - `amenityHighlights`
  - `availabilityStatus`

**Fix**: Add missing fields to fragment

---

### Issue #11: Rate Type & Layout Labels Don't Display

**Severity**: HIGH
**Impact**: Pricing and layout information shows raw values instead of friendly labels

**Problem**:
- Backend returns: `"hourly"`, `"full_day"`, `"theater"`, `"u_shape"` (lowercase)
- Frontend lookups expect: `"HOURLY"`, `"FULL_DAY"`, `"THEATER"`, `"U_SHAPE"` (uppercase)
- `RATE_TYPE_LABELS` and `LAYOUT_LABELS` object lookups fail
- Displays raw enum values to users instead of "Hourly", "Theater Style", etc.

**Affected Files**:
- Space pricing display components
- Venue detail pages showing layouts

**Fix**: Add `.toUpperCase()` normalization before lookup, similar to VenueStatusBadge pattern

---

## MEDIUM PRIORITY ISSUES (Missing/Incomplete Features)

### Issue #12: checkExistingWaitlist Query - No Backend Implementation

**Severity**: MEDIUM
**Impact**: Frontend query throws "Field not found" error

**Problem**:
- Frontend defines: `query CheckExistingWaitlist($venueId: String!) { checkExistingWaitlist(venueId: $venueId) { ... } }`
- Backend has NO resolver for this query
- GraphQL schema validation error

**Affected Files**:
- Frontend: `globalconnect/src/graphql/waitlist-queries.ts`
- Backend: Missing in `event-lifecycle-service/app/graphql/venue_waitlist_queries.py`

**Fix**: Implement backend resolver and register in queries.py

---

### Issue #13: Venue Dashboard Stats - Hardcoded Placeholders

**Severity**: MEDIUM
**Impact**: Venue owner dashboard shows no useful metrics

**Problem**:
- File: `globalconnect/src/app/(platform)/my-venues/[venueId]/page.tsx`
- All 4 stat cards hardcoded to `"--"`
  - RFPs Received: "--"
  - Responses Sent: "--"
  - Conversion Rate: "--"
  - Active Waitlist: "--"
- `GET_VENUE_OWNER_STATS_QUERY` exists but is not used

**Fix**: Wire up the stats query or implement per-venue stats fetching

---

### Issue #14: resolveWaitlistCircuitBreaker - Type Mismatch

**Severity**: MEDIUM
**Impact**: Resolving circuit breakers fails with type error

**Problem**:
- Frontend expects: scalar/boolean return value
- Backend returns: `ResolveCircuitBreakerResponse` object with multiple fields
- Additionally: `message` field is required in type but never provided in mutation response

**Affected Files**:
- Frontend: `globalconnect/src/graphql/waitlist-mutations.ts`
- Backend: `event-lifecycle-service/app/graphql/venue_waitlist_mutations.py`
- Backend: `event-lifecycle-service/app/graphql/venue_waitlist_types.py:242`

**Fix**:
1. Add `message` field to response construction
2. Update frontend to handle object response OR simplify backend to return boolean

---

### Issue #15: clearVenueAvailabilityOverride - Extra Fields

**Severity**: MEDIUM
**Impact**: GraphQL field error when clearing availability override

**Problem**:
- Frontend requests: `lastInferredAt` and `inferredStatus` in mutation response
- Backend `ClearOverrideResponse` only has: `success`, `venueId`, `availabilityStatus`, `isManualOverride`, `revertedToInferred`
- Missing fields cause GraphQL validation error

**Affected Files**:
- Frontend: `globalconnect/src/graphql/venues.graphql.ts` (CLEAR_VENUE_AVAILABILITY_OVERRIDE)
- Backend: `event-lifecycle-service/app/graphql/venue_types.py` (ClearOverrideResponse)

**Fix Options**:
1. Remove extra fields from frontend mutation
2. Add fields to backend response type

---

### Issue #16: Orphaned Component - Dead Code

**Severity**: LOW
**Impact**: Code bloat, maintenance confusion

**Problem**:
- File: `globalconnect/src/app/(platform)/my-venues/_components/edit-venue-modal.tsx`
- Simplified edit modal with only `name` and `address` fields
- Never imported or used anywhere (full edit page is used instead)
- Dead code

**Fix**: Remove file or add clear comment marking as deprecated/unused

---

### Issue #17: Duplicate Mutation Definitions

**Severity**: LOW
**Impact**: Maintenance confusion, potential inconsistencies

**Problem**:
- `CREATE_VENUE_MUTATION` defined in 2 files:
  - `globalconnect/src/graphql/venues.graphql.ts` (operation: `CreateVenue`)
  - `globalconnect/src/graphql/venue-management.graphql.ts` (operation: `CreateVenueDirectory`)
- `UPDATE_VENUE_MUTATION` also defined in both files
- Different return field sets, causes confusion about which to use

**Fix**: Consolidate into single definition per mutation, update all imports

---

## SUMMARY BY PRIORITY

### Must Fix First (Prevents Basic Usage):
1. ✅ Issue #3 - Build error (COUNTRY_CODES)
2. ✅ Issue #1 - Status case mismatch

### Critical Data Issues:
3. Issue #2 - My venues page empty state
4. Issue #7 - Dashboard edit button 404
5. Issue #4 - Waitlist parameter mismatches
6. Issue #6 - Admin queue missing data
7. Issue #8 - Listing cards missing data

### High Priority Enhancements:
8. Issue #9 - availabilityStatus mapping
9. Issue #10 - Directory card fragment
10. Issue #11 - Label lookups
11. Issue #5 - convertWaitlistHold types

### Feature Completion:
12. Issue #13 - Dashboard stats
13. Issue #12 - checkExistingWaitlist implementation
14. Issue #14 - resolveCircuitBreaker types
15. Issue #15 - clearAvailability extra fields

### Code Quality:
16. Issue #16 - Remove dead code
17. Issue #17 - Deduplicate mutations

---

## ESTIMATED FIX TIME

- **Phase 1** (Issues #1-3): ~30 minutes
- **Phase 2** (Issues #4-8): ~2 hours
- **Phase 3** (Issues #9-11): ~1 hour
- **Phase 4** (Issues #12-15): ~2 hours
- **Phase 5** (Issues #16-17): ~30 minutes

**Total**: ~6 hours for all fixes

---

## TESTING CHECKLIST

After fixes, verify:
- [ ] Create new venue page loads without errors
- [ ] My venues page shows existing venues
- [ ] Status badges display correctly
- [ ] Venue stats show actual counts
- [ ] Submit for review button enables for complete drafts
- [ ] Admin queue shows organization and verification data
- [ ] Venue listing cards show photos, spaces, prices
- [ ] Directory cards show all data
- [ ] Edit button routes correctly
- [ ] Waitlist operations work
- [ ] Rate type and layout labels display friendly text
- [ ] Availability status shows correctly
