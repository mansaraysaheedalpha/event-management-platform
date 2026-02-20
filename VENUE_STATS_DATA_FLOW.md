# Venue Stats Data Flow

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js/React)                    │
│  /my-venues/[venueId]/page.tsx                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  useQuery(VENUE_STATS_QUERY, { variables: { venueId } })            │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │
│  │  RFPs Received │  │ Responses Sent │  │ Conversion Rate│        │
│  │      {stat}    │  │      {stat}    │  │     {stat}%    │        │
│  └────────────────┘  └────────────────┘  └────────────────┘        │
│                                                                      │
│  ┌────────────────┐                                                 │
│  │Active Waitlist │                                                 │
│  │     {stat}     │                                                 │
│  └────────────────┘                                                 │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           │ GraphQL Query
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    GRAPHQL LAYER (Strawberry)                       │
│  app/graphql/queries.py                                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  @strawberry.field                                                  │
│  def venueStats(self, venueId: str, info: Info) -> VenueStatsType  │
│                                                                      │
│      └─► venue_queries.venue_stats_query(info, venueId)             │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      RESOLVER LOGIC                                 │
│  app/graphql/venue_queries.py                                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  def venue_stats_query(info: Info, venue_id: str):                 │
│                                                                      │
│    1. Verify Authorization                                          │
│       ├─► Check user.orgId exists                                   │
│       └─► Verify venue.organization_id == user.orgId                │
│                                                                      │
│    2. Query Database                                                │
│       ├─► Count RFPVenue(venue_id=X)                                │
│       ├─► Count RFPVenue(venue_id=X, status NOT IN [received/viewed])│
│       ├─► Count RFPVenue(venue_id=X, status IN [awarded/selected])  │
│       └─► Count VenueWaitlistEntry(venue_id=X, status IN [waiting/offered])│
│                                                                      │
│    3. Calculate Stats                                               │
│       └─► conversionRate = (wins / total) * 100                     │
│                                                                      │
│    4. Return VenueStatsType                                         │
│       └─► { rfpsReceived, responsesSent, conversionRate, activeWaitlistCount }│
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           │ SQL Queries
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        DATABASE (PostgreSQL)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐              ┌──────────────────────────┐    │
│  │   rfp_venues     │              │ venue_waitlist_entries   │    │
│  ├──────────────────┤              ├──────────────────────────┤    │
│  │ id               │              │ id                       │    │
│  │ rfp_id           │              │ organization_id          │    │
│  │ venue_id         │◄─────────────│ venue_id                 │    │
│  │ status           │              │ status                   │    │
│  │ notified_at      │              │ desired_dates_start      │    │
│  │ viewed_at        │              │ attendance_min           │    │
│  │ responded_at     │              │ ...                      │    │
│  │ ...              │              └──────────────────────────┘    │
│  └──────────────────┘                                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Mapping

### 1. RFPs Received
```sql
SELECT COUNT(*)
FROM rfp_venues
WHERE venue_id = :venue_id
```

### 2. Responses Sent
```sql
SELECT COUNT(*)
FROM rfp_venues
WHERE venue_id = :venue_id
  AND status NOT IN ('received', 'viewed')
```

### 3. Conversion Rate
```sql
-- Count wins
SELECT COUNT(*)
FROM rfp_venues
WHERE venue_id = :venue_id
  AND status IN ('awarded', 'selected', 'booked')

-- Calculate: (wins / total) * 100
-- Returns NULL if total = 0
```

### 4. Active Waitlist Count
```sql
SELECT COUNT(*)
FROM venue_waitlist_entries
WHERE venue_id = :venue_id
  AND status IN ('waiting', 'offered')
```

## Status Flows

### RFPVenue Status Progression
```
received → viewed → responded → shortlisted → awarded
                         ↓
                    declined
```

### VenueWaitlistEntry Status Progression
```
waiting → offered → converted
    ↓         ↓
cancelled   expired
```

## Security Flow

```
User Request
     ↓
Extract JWT Token
     ↓
Decode user.orgId
     ↓
Fetch Venue(id=venueId)
     ↓
venue.organization_id == user.orgId?
     ↓              ↓
   YES            NO
     ↓              ↓
Return Stats   403 Forbidden
```

## Error Handling

### Frontend
- Loading State: Shows "--" or Skeleton
- No Data: Shows "0" or "N/A"
- Error State: Alert with error message

### Backend
- Unauthorized: HTTPException(403, "Not authorized")
- Venue Not Found: HTTPException(403, "Not authorized to view this venue's stats")
- No RFPs: conversionRate = None (displayed as "N/A")
- Database Error: Propagates to frontend as GraphQL error
