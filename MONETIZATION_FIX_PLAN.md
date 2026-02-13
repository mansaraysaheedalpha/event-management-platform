# Monetization Feature — Production Fix Plan

> Generated from full audit of frontend, backend, GraphQL, and real-time layers.
> Each phase is self-contained and can be deployed to 1-3 agents depending on parallelism.

---

## Phase 1 — Critical Backend Fixes (Security + Data Integrity)

**Deploy: 2 agents in parallel (1A + 1B)**

### Agent 1A Prompt:

```
You are fixing critical security and data integrity issues in the monetization backend of an event management platform.

CONTEXT: This is a Python/FastAPI backend (event-lifecycle-service) using SQLAlchemy, PostgreSQL, Redis, and Stripe. The GraphQL layer uses Strawberry.

BEFORE WRITING ANY CODE: Read and understand these files thoroughly:
- event-lifecycle-service/app/api/v1/endpoints/offers.py (entire file — focus on purchase flow lines 287-437)
- event-lifecycle-service/app/api/v1/endpoints/analytics.py (entire file)
- event-lifecycle-service/app/graphql/offer_mutations.py (purchase_offer mutation)
- event-lifecycle-service/app/crud/crud_offer.py (reserve_inventory, check_availability)
- event-lifecycle-service/app/services/offer_reservation_service.py (entire file)
- event-lifecycle-service/app/background_tasks/offer_tasks.py (entire file)
- event-lifecycle-service/app/models/offer.py
- event-lifecycle-service/app/models/offer_purchase.py

THEN implement these fixes with elite engineering:

1. OFFER PURCHASE IDOR FIX: In the purchase endpoint (offers.py ~line 287) and the GraphQL purchaseOffer mutation, add verification that the offer's event_id belongs to an event the user is registered for or that is public. Use the existing verify_event_access() helper. The user should not be able to purchase an offer just by knowing the offer_id.

2. ANALYTICS AUTH FIX: In analytics.py, the monetization analytics endpoint (~line 140) has a TODO for event access verification. Implement it — verify the requesting user is the event owner or belongs to the event's organization before returning data. Use the same pattern as other protected endpoints in the codebase.

3. INVENTORY CLEANUP SCHEDULER: The cleanup_stale_reservations() task in offer_tasks.py exists but is not integrated with any scheduler. Wire it up:
   - Find how other background tasks are scheduled in this project (look for Celery beat, APScheduler, or FastAPI startup events)
   - Register cleanup_stale_reservations to run every 5 minutes
   - Also register auto_expire_offers to run every 30 minutes
   - Both tasks already exist — you just need to schedule them

4. OFFER PRICE VALIDATION: Add server-side validation in both the REST endpoint (offers.py POST /) and GraphQL mutation (offer_mutations.py create_offer):
   - price must be >= 0
   - quantity on purchase must be >= 1 and <= 20
   - if original_price is set, it must be >= price
   - if inventory_total is set, it must be >= 1
   These constraints exist as DB CHECK constraints in the migration but are not validated before hitting the DB. Add proper Pydantic/input validation so users get clear error messages.

5. OFFER FULFILLMENT STUBS: In offer_tasks.py, the fulfillment processors for TICKET_UPGRADE, PHYSICAL, and SERVICE types are TODOs. For now, implement sensible minimal versions:
   - TICKET_UPGRADE: Update fulfillment_status to PROCESSING, log that manual intervention needed, mark as FULFILLED with a note
   - PHYSICAL: Update to PROCESSING, generate a placeholder tracking reference, mark FULFILLED
   - SERVICE: Update to PROCESSING, mark FULFILLED with a "service scheduled" note
   - The key is these should NOT stay PENDING forever — move them through the pipeline even if the actual integration is manual for now

Ensure all changes maintain existing test patterns. Do NOT break any existing functionality.
```

### Agent 1B Prompt:

```
You are fixing critical security and async issues in the waitlist backend of an event management platform.

CONTEXT: This is a Python/FastAPI backend (event-lifecycle-service) using SQLAlchemy, PostgreSQL, Redis, and JWT tokens. The real-time layer is a NestJS service.

BEFORE WRITING ANY CODE: Read and understand these files thoroughly:
- event-lifecycle-service/app/api/v1/endpoints/waitlist.py (entire file — focus on DELETE endpoint ~lines 175-323)
- event-lifecycle-service/app/api/v1/endpoints/admin_waitlist.py (entire file — focus on bulk-send-offers ~lines 595-734, manual offer ~lines 367-462)
- event-lifecycle-service/app/utils/waitlist.py (all utility functions)
- event-lifecycle-service/app/utils/waitlist_analytics.py
- event-lifecycle-service/app/models/session_waitlist.py
- event-lifecycle-service/app/models/session_capacity.py
- event-lifecycle-service/app/crud/crud_session_capacity.py
- event-lifecycle-service/app/graphql/waitlist_mutations.py
- event-lifecycle-service/app/api/v1/endpoints/ads.py (ad serving — focus on frequency cap ~lines 175-189)

THEN implement these fixes with elite engineering:

1. ASYNC/SYNC FIX: In waitlist.py ~line 291, there is an asyncio.run() call inside a sync endpoint that blocks the entire worker thread. Fix this properly:
   - If the endpoint is sync (def, not async def), use FastAPI's BackgroundTasks to dispatch the Kafka publish and user service calls
   - OR convert the endpoint to async def and use await directly
   - Check which pattern the rest of the codebase uses and be consistent
   - This same pattern may exist in other waitlist endpoints — fix all occurrences

2. WAITLIST NOTIFICATION SENDING: In admin_waitlist.py, the "Send Offer" (~line 460) and "Bulk Send Offers" (~line 723) endpoints have TODOs for sending notifications. Implement them:
   - Look at how other notifications are sent in this project (check for Kafka producers, email services, or the email-consumer-worker)
   - Publish a Kafka event for each offer sent, containing: user_id, email, session details, offer token, expiry timestamp
   - Use the same Kafka topic and event schema as the existing waitlist offer event in waitlist.py
   - If a direct email service exists (like Resend), use that as a fallback
   - Also implement the "offer next person" logic in the admin remove endpoint (~line 267) where the TODO exists

3. AD FREQUENCY CAP FAIL-OPEN FIX: In ads.py ~lines 175-189, if Redis is down, the ad serving endpoint skips frequency capping entirely and shows all ads. Fix this:
   - On Redis failure, apply a conservative fallback: return only 1 ad instead of the requested limit
   - Log the Redis failure as a warning
   - Add a circuit breaker pattern or at minimum a flag that indicates degraded mode
   - Do NOT let Redis failures result in unlimited ad impressions

4. AD URL VALIDATION: In the ad creation endpoint and GraphQL mutation:
   - Validate media_url and click_url are valid URLs with http:// or https:// protocol
   - Reject javascript:, data:, and other dangerous URI schemes
   - Validate URL length (max 2048 chars)
   - Look for existing URL validation helpers in the codebase (check app/utils/security.py) and reuse them

5. WAITLIST PRIORITY TIER: In waitlist.py ~line 133, the map_ticket_to_priority() function defaults everyone to STANDARD. Implement basic tier mapping:
   - Look at how ticket tiers are stored in this project (check ticket/order models)
   - Map VIP tickets to VIP priority, Premium to PREMIUM, everything else to STANDARD
   - If ticket tier data is not available at waitlist join time, accept an optional priority_tier in the join request input that organizers can configure per-session

Ensure all changes maintain existing patterns. Do NOT break any existing functionality.
```

---

## Phase 2 — Frontend Fixes + Missing Implementations

**Deploy: 2 agents in parallel (2A + 2B)**

### Agent 2A Prompt:

```
You are fixing critical frontend issues in the monetization tab of an event management organizer dashboard.

CONTEXT: This is a Next.js frontend (globalconnect directory) using Apollo Client for GraphQL, Recharts for charts, shadcn/ui components, and Stripe for payments. The monetization tab has 4 sub-tabs: Revenue Insights, Ads Management, Upsells (Offers), and Waitlist Management.

BEFORE WRITING ANY CODE: Read and understand these files thoroughly:
- globalconnect/src/app/(platform)/dashboard/events/[eventId]/monetization/page.tsx
- globalconnect/src/app/(platform)/dashboard/events/[eventId]/monetization/upsells.tsx
- globalconnect/src/app/(platform)/dashboard/events/[eventId]/monetization/ads.tsx
- globalconnect/src/app/(platform)/dashboard/events/[eventId]/monetization/waitlist.tsx
- globalconnect/src/components/features/waitlist/waitlist-management-table.tsx
- globalconnect/src/app/(platform)/dashboard/events/[eventId]/analytics/_components/scheduled-reports.tsx
- globalconnect/src/lib/export-utils.ts
- globalconnect/src/hooks/use-export-analytics.ts
- globalconnect/src/graphql/monetization.graphql.ts
- globalconnect/src/app/(platform)/dashboard/events/[eventId]/analytics/_components/export-report-dialog.tsx

THEN implement these fixes with elite engineering:

1. SCHEDULED REPORTS — REMOVE OR MARK AS COMING SOON: The scheduled-reports.tsx component is entirely fake (hardcoded mock data, client-side state only, no backend). Since there is no backend for this feature:
   - Replace the full interactive form with a clean "Coming Soon" card that shows the feature concept
   - Keep the component file but gut the fake CRUD operations
   - Show a brief description: "Automated report delivery via email — daily, weekly, or monthly"
   - Add a subtle badge like "Coming Soon" using the existing Badge component
   - Remove the fake scheduled report entries and the create/delete/toggle logic
   - This prevents users from thinking they configured reports that silently do nothing

2. EXPORT FIXES — REAL EXCEL + HONEST PDF:
   - In export-utils.ts, install and use the `xlsx` library (SheetJS) for proper Excel export:
     - Create a workbook with separate sheets for each analytics section
     - Add proper headers, number formatting, and column widths
     - The CSV export already has the data structure — adapt it for xlsx
   - For PDF export: since server-side generation is complex, take the pragmatic approach:
     - Use the browser's built-in print-to-PDF via window.print() with a print-optimized view
     - Create a hidden printable div with the analytics data styled for print
     - Trigger window.print() and let the browser handle PDF generation
     - OR remove "PDF" as an option from the export dialog and keep only CSV + Excel
   - Update the export-report-dialog.tsx to reflect what actually works
   - Remove the A/B Test Results section from the export dialog (line 86-90) since it's not implemented

3. UPSELLS FORM VALIDATION: In upsells.tsx:
   - Add proper price validation: must be a valid number >= 0, max 999999.99
   - parseFloat("1.5.5") returns 1.5 silently — add explicit regex validation for decimal numbers
   - If original_price is set, validate it >= price
   - If inventory_total is set, validate it >= 1
   - Add URL validation for image_url (optional field but if provided must be valid https URL)
   - Show inline error messages using the existing form error pattern in the codebase
   - Prevent form submission while validation errors exist

4. ADS FORM VALIDATION: In ads.tsx:
   - Add URL validation for mediaUrl and clickUrl — must be valid http:// or https:// URLs
   - Add name length validation (1-200 chars)
   - Show inline validation errors
   - Prevent form submission with invalid data

5. DATE RANGE CROSS-VALIDATION: In the date-range-picker.tsx:
   - Ensure "from" date cannot be after "to" date
   - If user changes "from" to be after "to", automatically adjust "to" to match "from"
   - Add max range limit of 365 days to prevent massive data fetches

Ensure all changes compile without TypeScript errors and maintain existing UI patterns.
```

### Agent 2B Prompt:

```
You are fixing critical performance and real-time update issues in the waitlist management frontend and the GraphQL schema layer.

CONTEXT: This is a Next.js frontend (globalconnect directory) using Apollo Client, Socket.io for real-time, and shadcn/ui. The backend is Python/FastAPI with Strawberry GraphQL.

BEFORE WRITING ANY CODE: Read and understand these files thoroughly:
- globalconnect/src/components/features/waitlist/waitlist-management-table.tsx (entire file)
- globalconnect/src/components/features/waitlist/waitlist-capacity-manager.tsx
- globalconnect/src/components/features/waitlist/waitlist-analytics.tsx
- globalconnect/src/app/(platform)/dashboard/events/[eventId]/monetization/ads.tsx (lines 211-220 for perf map)
- globalconnect/src/hooks/use-monetization.ts
- event-lifecycle-service/app/graphql/types.py (AdType ~lines 684-703, OfferType ~lines 705-789)
- event-lifecycle-service/app/graphql/queries.py (adsForContext query, monetization_analytics query)
- event-lifecycle-service/app/graphql/dataloaders.py

THEN implement these fixes with elite engineering:

1. WAITLIST TABLE PAGINATION: In waitlist-management-table.tsx:
   - Add client-side pagination with 25 entries per page
   - Use the existing shadcn/ui pagination components or a simple prev/next with page numbers
   - Show total count and current page range ("Showing 1-25 of 342")
   - Maintain real-time update behavior — when data refetches, stay on current page unless entries shift
   - Add a search/filter input to filter by user name or email

2. DEBOUNCE REAL-TIME REFETCHES: In waitlist-management-table.tsx:
   - Currently 6 WebSocket events each independently trigger refetch() + toast
   - Implement a debounced refetch: batch all events within a 1-second window into a single refetch
   - Use a useRef + setTimeout pattern or a debounce utility
   - For toasts: show at most 1 toast per 3 seconds summarizing changes ("Waitlist updated: 3 new entries")
   - Count the batched events and show a single summary toast

3. SOCKET ERROR HANDLING: In waitlist-management-table.tsx and use-monetization.ts:
   - Add error handling for socket.emit("join_room") — handle connection failures
   - Add reconnection logic: if socket disconnects, show a subtle "Reconnecting..." indicator
   - On reconnect, rejoin the room and trigger a fresh refetch
   - Clean up event listeners properly on unmount to prevent handler stacking on remount

4. MEMOIZE EXPENSIVE COMPUTATIONS:
   - In ads.tsx lines 211-220: wrap the adPerformanceMap creation in useMemo with proper dependency on adAnalytics
   - In waitlist-analytics.tsx: memoize the funnel percentage calculations
   - In revenue-insights.tsx: memoize metric card calculations

5. GRAPHQL SCHEMA COMPLETENESS: In event-lifecycle-service/app/graphql/types.py:
   - Add missing fields to AdType: starts_at (Optional[datetime]), ends_at (Optional[datetime]), is_active (bool), placements (List[str]), target_sessions (List[str]), frequency_cap (Optional[int]), aspect_ratio (Optional[str])
   - Fix the OfferType.inventory resolver (lines 731-754) — it has dual dict/ORM branching. Normalize it to always work with ORM objects. If dicts come from somewhere, convert them to a consistent NamedTuple or dataclass before reaching the resolver
   - Add is_active field to OfferType
   - Add starts_at field to OfferType if missing from the type definition (it exists as a resolver)
   - Update the corresponding frontend GraphQL query fragments in globalconnect/src/graphql/monetization.graphql.ts to request the new fields where useful (especially is_active and scheduling fields for ads)

Ensure all changes compile/run without errors. Backend changes should not break existing queries.
```

---

## Phase 3 — Resilience, Observability, and Polish

**Deploy: 1 agent (can be done sequentially after Phase 1 + 2 are verified)**

### Agent 3 Prompt:

```
You are adding resilience, observability, and final polish to the monetization features of an event management platform. Phases 1 and 2 have already fixed critical bugs, security issues, and missing implementations.

CONTEXT: Python/FastAPI backend (event-lifecycle-service), NestJS real-time service, Next.js frontend (globalconnect). Uses PostgreSQL, Redis, Kafka, Stripe, Apollo Client, Socket.io.

BEFORE WRITING ANY CODE: Read and understand these files to see what Phase 1 and 2 already changed:
- event-lifecycle-service/app/api/v1/endpoints/ads.py
- event-lifecycle-service/app/api/v1/endpoints/offers.py
- event-lifecycle-service/app/api/v1/endpoints/waitlist.py
- event-lifecycle-service/app/api/v1/endpoints/admin_waitlist.py
- event-lifecycle-service/app/background_tasks/offer_tasks.py
- event-lifecycle-service/app/graphql/types.py
- event-lifecycle-service/app/graphql/queries.py
- globalconnect/src/components/features/waitlist/waitlist-management-table.tsx
- globalconnect/src/app/(platform)/dashboard/events/[eventId]/monetization/upsells.tsx
- globalconnect/src/app/(platform)/dashboard/events/[eventId]/monetization/ads.tsx
- globalconnect/src/app/(platform)/dashboard/events/[eventId]/monetization/revenue-insights.tsx
- globalconnect/src/lib/export-utils.ts
- real-time-service/src/monetization/waitlist/waitlist.service.ts

THEN implement these improvements with elite engineering:

1. REDIS CONSISTENCY FIX (NestJS vs Python): The real-time-service waitlist.service.ts uses Redis LIST (RPUSH/LPOP) for waitlist queue, but the Python backend uses Redis ZSET (ZADD/ZRANK) with priority tiers. These are incompatible data structures for the same logical queue. Fix this:
   - Update the NestJS waitlist service to use ZSET operations matching the Python backend
   - Use the same key format: waitlist:session:{session_id}:{tier}
   - Use timestamp as score (same as Python side)
   - Ensure both services can read/write the same Redis keys without corruption

2. MISSING DATABASE INDEXES: Add indexes that are missing for production query patterns:
   - ad_events table: composite index on (ad_id, event_type, created_at) for analytics aggregation
   - monetization_events table: composite index on (event_id, event_type, created_at) for funnel queries
   - offer_purchases table: composite index on (offer_id, fulfillment_status) for pending fulfillment batch queries
   - Create a new Alembic migration for these indexes
   - Use CREATE INDEX CONCURRENTLY pattern if supported to avoid table locks

3. N+1 QUERY FIX: In event-lifecycle-service/app/crud/crud_offer.py, the get_active_offers() method (~lines 82-84) filters inventory availability in a Python loop instead of SQL. Fix this:
   - Move the inventory availability check into the SQL WHERE clause: inventory_total IS NULL OR (inventory_total - inventory_sold - inventory_reserved) > 0
   - This eliminates fetching offers that are sold out just to discard them in Python

4. AD SERVING QUERY OPTIMIZATION: In event-lifecycle-service/app/graphql/queries.py, the adsForContext query fetches ALL ads for an event then filters in Python. Optimize this:
   - Push placement, scheduling (NOW() BETWEEN starts_at AND ends_at), and active status filters into the SQL query
   - Use the existing get_active_ads() CRUD method which already has these filters
   - Only do weighted selection in Python (that's fine)

5. FRONTEND ERROR BOUNDARIES: Add React error boundaries around the analytics chart components to prevent a single chart crash from taking down the entire monetization tab:
   - Create a reusable ChartErrorBoundary component that shows a "Failed to load chart" fallback with a retry button
   - Wrap these components: RevenueOverview, OfferPerformance, AdCampaignAnalytics, WaitlistMetrics, ConversionFunnel
   - The error boundary should catch rendering errors in Recharts components specifically

6. ACCESSIBILITY PASS on the waitlist management table:
   - Add scope="col" to all <th> elements
   - Add aria-label to icon-only buttons (trash, send offer, checkmark)
   - Add aria-live="polite" to the table container so screen readers announce real-time updates
   - Add aria-invalid and aria-describedby to form inputs in the capacity manager
   - Ensure status badges have accessible text (not just color coding)

7. CENTS-TO-DOLLARS CONSISTENCY: Create a single shared utility function for currency formatting and use it everywhere:
   - In globalconnect/src/lib/format-utils.ts (or similar), create: formatCurrency(cents: number, currency?: string): string
   - It should handle: cents to dollars conversion, locale formatting, currency symbol
   - Replace all inline `/ 100` and `toLocaleString()` calls in:
     - revenue-insights.tsx
     - revenue-overview.tsx
     - offer-performance.tsx
     - purchased-offers-list.tsx
   - This prevents bugs from inconsistent conversion

Ensure all changes compile/run without errors. Create proper Alembic migrations for any DB changes.
```

---

## Deployment Order

```
Phase 1A + 1B  ──► run in parallel  ──► verify backend works
      │
      ▼
Phase 2A + 2B  ──► run in parallel  ──► verify frontend works
      │
      ▼
Phase 3        ──► single agent     ──► final polish + verify full flow
```

## How to Use This Plan

1. Copy the agent prompt for the phase you want to deploy
2. Paste it as the first message to a fresh Claude Code agent
3. The agent will read the specified files, understand context, and implement the fixes
4. After each phase, do a quick smoke test of the monetization tab before proceeding

## Risk Notes

- Phase 1 changes backend behavior — test Stripe webhook flow after deploying
- Phase 2A removes the scheduled reports UI — if stakeholders expect it, discuss first
- Phase 3 changes Redis data structures — coordinate NestJS and Python deployments together
- All phases are designed to be non-breaking incrementally, but full integration testing after Phase 3 is strongly recommended