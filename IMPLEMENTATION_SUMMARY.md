# Issue #13: Venue Dashboard Stats Implementation

## Summary
Successfully implemented a full-stack solution to display real venue statistics on the venue owner dashboard, replacing hardcoded "--" values with live data.

## Changes Made

### Backend (event-lifecycle-service)

#### 1. Added VenueStatsType in `app/graphql/venue_types.py`
- **Type**: `VenueStatsType`
- **Fields**:
  - `rfpsReceived: int` - Total RFPs that include this venue
  - `responsesSent: int` - Venue owner's responses to RFPs (status != 'received' or 'viewed')
  - `conversionRate: Optional[float]` - Percentage of RFPs won (null if no RFPs)
  - `activeWaitlistCount: int` - Current waitlist entries with status 'waiting' or 'offered'

#### 2. Implemented Query Resolver in `app/graphql/venue_queries.py`
- **Function**: `venue_stats_query(info: Info, venue_id: str) -> VenueStatsType`
- **Authorization**: Requires venue ownership (verifies venue.organization_id matches user's orgId)
- **Statistics Calculation**:
  - **RFPs Received**: Count of all RFPVenue records for this venue
  - **Responses Sent**: Count of RFPVenue records with status NOT in ['received', 'viewed']
  - **Conversion Rate**: (RFPs with status in ['awarded', 'selected', 'booked']) / total RFPs * 100
  - **Active Waitlist**: Count of VenueWaitlistEntry with status in ['waiting', 'offered']

#### 3. Registered Query in `app/graphql/queries.py`
- **Query Field**: `venueStats(venueId: str) -> VenueStatsType`
- **Location**: Line 463 in queries.py
- Imported `VenueStatsType` from venue_types
- Delegates to `venue_queries.venue_stats_query()`

### Frontend (globalconnect)

#### 1. Created GraphQL Query in `src/graphql/venues.graphql.ts`
```graphql
query VenueStats($venueId: String!) {
  venueStats(venueId: $venueId) {
    rfpsReceived
    responsesSent
    conversionRate
    activeWaitlistCount
  }
}
```

#### 2. Updated Dashboard Component in `src/app/(platform)/my-venues/[venueId]/page.tsx`
- Added `VenueStatsData` type definition
- Imported `VENUE_STATS_QUERY` from venues.graphql.ts
- Added `useQuery` hook to fetch stats data
- Implemented `formatConversionRate()` helper function:
  - Returns "N/A" when conversionRate is null (no RFPs)
  - Returns percentage string (e.g., "23.5%") otherwise
- Updated StatCard components to display real data:
  - RFPs Received: `stats.rfpsReceived`
  - Responses Sent: `stats.responsesSent`
  - Conversion Rate: Formatted percentage or "N/A"
  - Active Waitlist: `stats.activeWaitlistCount`
- Added loading state support to StatCard component with Skeleton

## Key Features

### Error Handling
- ✅ Unauthorized access returns 403 error
- ✅ Invalid venue ID returns 403 error
- ✅ Null conversion rate handled gracefully (shows "N/A")

### Edge Cases Handled
- ✅ Venue with no RFPs: Shows 0 for counts, "N/A" for conversion rate
- ✅ Venue with no waitlist entries: Shows 0
- ✅ Venue with RFPs but no wins: Shows 0% conversion rate
- ✅ Loading states: Shows "--" or skeleton while data loads

### Authorization
- ✅ Only venue owners can view stats for their venues
- ✅ Verifies organization_id matches user's orgId
- ✅ Returns 403 if unauthorized

## Testing Checklist

### Backend Testing
- [x] VenueStatsType properly defined with correct fields
- [x] venue_stats_query function exists with correct signature
- [x] venueStats query registered in GraphQL schema
- [x] Python syntax validation passes
- [ ] Authorization logic tested (requires venue ownership)
- [ ] Stats calculation tested with sample data
- [ ] Edge cases tested (no RFPs, no waitlist, etc.)

### Frontend Testing
- [x] VENUE_STATS_QUERY properly defined
- [x] Dashboard component imports and uses query
- [x] TypeScript types defined correctly
- [ ] UI displays loading state correctly
- [ ] UI displays real data when loaded
- [ ] UI handles null conversion rate (shows "N/A")
- [ ] UI handles error states

## Files Modified

### Backend
1. `event-lifecycle-service/app/graphql/venue_types.py` - Added VenueStatsType
2. `event-lifecycle-service/app/graphql/venue_queries.py` - Added venue_stats_query resolver
3. `event-lifecycle-service/app/graphql/queries.py` - Registered venueStats query

### Frontend
4. `globalconnect/src/graphql/venues.graphql.ts` - Added VENUE_STATS_QUERY
5. `globalconnect/src/app/(platform)/my-venues/[venueId]/page.tsx` - Wired up stats display

## Database Schema Used

### RFPVenue (app/models/rfp_venue.py)
- Tracks RFPs sent to venues
- Key fields: `venue_id`, `status`, `rfp_id`
- Statuses: received, viewed, responded, shortlisted, awarded, declined

### VenueWaitlistEntry (app/models/venue_waitlist_entry.py)
- Tracks organizers waiting for venue availability
- Key fields: `venue_id`, `status`, `organization_id`
- Statuses: waiting, offered, converted, expired, cancelled

## Next Steps

To fully test this implementation:

1. **Backend Testing**:
   - Run the event-lifecycle-service
   - Use GraphQL playground to test the venueStats query
   - Verify authorization works correctly
   - Test with venues that have different data scenarios

2. **Frontend Testing**:
   - Run the globalconnect application
   - Navigate to a venue dashboard (`/my-venues/[venueId]`)
   - Verify stats display correctly
   - Test loading states
   - Test error handling

3. **Integration Testing**:
   - Create test RFPs for a venue
   - Verify RFPs Received increases
   - Respond to RFPs and verify Responses Sent increases
   - Award an RFP and verify Conversion Rate updates
   - Join waitlist and verify Active Waitlist count increases

## Implementation Notes

- Conversion rate is calculated as percentage and rounded to 1 decimal place
- Null conversion rate (no RFPs) is handled separately to avoid division by zero
- Authorization checks happen before any database queries for security
- Frontend uses separate loading state for stats to avoid blocking venue details
- StatCard component supports optional loading prop for skeleton display
