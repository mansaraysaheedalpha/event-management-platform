# Async SQLAlchemy Rewrite Plan

> **Goal**: Convert event-lifecycle-service from synchronous SQLAlchemy to fully async SQLAlchemy 2.0 with `asyncpg`, enabling the system to handle **thousands of events** and **millions of attendees** efficiently.
>
> **Estimated Effort**: 3-4 weeks (full-time) | Can be done incrementally
>
> **Expected Impact**: 10-20% latency reduction per request, 3-5x higher concurrent request throughput under load

---

## Table of Contents

1. [Why This Rewrite Matters at Scale](#1-why-this-rewrite-matters-at-scale)
2. [Current State Analysis](#2-current-state-analysis)
3. [Migration Strategy](#3-migration-strategy)
4. [Phase 1: Foundation](#4-phase-1-foundation-2-3-days)
5. [Phase 2: Base CRUD Class](#5-phase-2-base-crud-class-1-2-days)
6. [Phase 3: CRUD Files](#6-phase-3-crud-files-5-7-days)
7. [Phase 4: API Endpoints](#7-phase-4-api-endpoints-3-4-days)
8. [Phase 5: GraphQL Layer](#8-phase-5-graphql-layer-3-4-days)
9. [Phase 6: Background Tasks & Services](#9-phase-6-background-tasks--services-2-3-days)
10. [Phase 7: Cleanup & Testing](#10-phase-7-cleanup--testing-2-3-days)
11. [File-by-File Checklist](#11-file-by-file-checklist)
12. [Key Code Transformations](#12-key-code-transformations)
13. [Risks & Mitigations](#13-risks--mitigations)
14. [Prerequisites](#14-prerequisites)

---

## 1. Why This Rewrite Matters at Scale

### The Problem

Right now, every database query **blocks** the entire Python thread until the database responds. FastAPI runs async, but when it hits a sync database call, it offloads to a thread pool (default 40 threads). This means:

| Metric | Current (Sync) | After Rewrite (Async) |
|--------|----------------|----------------------|
| Max concurrent DB queries | ~40 (thread pool limit) | ~1,000+ (event loop) |
| Memory per connection | ~8MB (thread stack) | ~few KB (coroutine) |
| Latency under load | Degrades fast at 100+ concurrent | Stable at 1,000+ concurrent |
| Thread pool exhaustion | Happens at ~200 req/s | Not applicable |

### At Your Target Scale

- **Thousands of events**: Each event page triggers 5-10 DB queries (event, sessions, speakers, venue, registrations, offers). With 1,000 concurrent users browsing events, that's 5,000-10,000 concurrent DB queries.
- **Millions of attendees**: Registration queries, ticket lookups, and real-time attendance tracking all hit the DB. Sync threads will bottleneck at ~200 concurrent operations.

### The Critical Issue Today

Your GraphQL layer already has **100+ async functions** that use **sync database sessions**. This means FastAPI is silently wrapping every DB call in `run_in_executor()`, adding overhead and limiting concurrency. The rewrite fixes this mismatch.

---

## 2. Current State Analysis

### Service Statistics

| Category | Files | Lines of Code | Conversion Needed |
|----------|-------|---------------|-------------------|
| CRUD files | 39 | ~7,779 | YES - All files |
| API endpoints | 29 | ~11,426 | YES - 22 sync, 7 partially async |
| GraphQL resolvers | 20 | ~9,439 | YES - Fix async/sync mismatch |
| Models | 48 | ~3,200 | NO - Models stay the same |
| Background tasks | 7 | ~1,664 | YES - All files |
| Services | 14 | ~2,889 | YES - All files |
| DB session | 1 | 35 | YES - Core change |
| **Total to convert** | **~110 files** | **~37,200 lines** | |

### Database Operations Count

- `db.query(...)` calls: **~280**
- `db.add(...)` calls: **~120**
- `db.commit()` calls: **~100**
- `db.rollback()` calls: **~30**
- `db.refresh(...)` calls: **~27**
- **Total sync DB operations: ~557**

### Sync httpx Calls (Also Need Async Conversion)

| File | Calls | Purpose |
|------|-------|---------|
| `app/background_tasks/session_reminder_tasks.py` | 2 | Sending reminder notifications |
| `app/utils/sponsor_notifications.py` | 9 | Sponsor notification webhooks |
| `app/services/realtime_client.py` | 2 | Real-time service HTTP calls |
| `app/api/v1/endpoints/sponsors.py` | 3 | Sponsor image uploads |
| `app/graphql/queries.py` | 2 | External service calls |

---

## 3. Migration Strategy

### Approach: Incremental (NOT Big-Bang)

The key insight is that **sync and async sessions can coexist**. You can convert one file at a time while keeping the rest sync. This means:

1. No deployment risk - each PR is small and testable
2. No feature freeze - other devs can keep working
3. Easy rollback - revert one file, not the whole service

### How It Works

```
Phase 1: Add async engine + async session alongside sync ones
Phase 2: Create async base CRUD class (keep sync base too)
Phase 3: Convert CRUD files one-by-one (both sync and async methods coexist)
Phase 4: Convert API endpoints to use async CRUD
Phase 5: Fix GraphQL async/sync mismatch
Phase 6: Convert background tasks
Phase 7: Remove sync engine, session, and old CRUD methods
```

---

## 4. Phase 1: Foundation (2-3 days)

### 4.1 Add asyncpg dependency

**File**: `requirements.txt`

```diff
  sqlalchemy
- psycopg2-binary
+ psycopg2-binary    # Keep for Alembic migrations (sync)
+ asyncpg             # Async PostgreSQL driver
```

> **Note**: Keep `psycopg2-binary` because Alembic migrations run synchronously and need it.

### 4.2 Create async engine and session

**File**: `app/db/session.py`

Convert from:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=50,
    pool_recycle=3600,
    pool_timeout=30,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

To:
```python
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker

# Convert postgres:// to postgresql+asyncpg://
def _get_async_url(url: str) -> str:
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)

# SYNC engine - keep for Alembic and gradual migration
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,       # Reduce since async will handle most traffic
    max_overflow=20,
    pool_recycle=3600,
    pool_timeout=30,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ASYNC engine - new primary engine
async_engine = create_async_engine(
    _get_async_url(settings.DATABASE_URL),
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=50,
    pool_recycle=3600,
    pool_timeout=30,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Important: prevents lazy-load issues
)

# Sync dependency (keep during migration)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Async dependency (new)
async def get_async_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

### 4.3 Update main.py lifespan

**File**: `app/main.py`

```python
from app.db.session import async_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Use async engine for startup checks
    async with async_engine.begin() as conn:
        # Optional: verify connection works
        await conn.execute(text("SELECT 1"))

    init_scheduler()
    yield

    shutdown_scheduler()
    shutdown_kafka_producer()
    # Dispose async engine on shutdown
    await async_engine.dispose()
```

### 4.4 Update deps.py

**File**: `app/api/deps.py`

```python
from app.db.session import get_async_db

# Add alongside existing get_db dependency
async def get_current_user_async(
    db: AsyncSession = Depends(get_async_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    # Same logic but using async session
    ...
```

---

## 5. Phase 2: Base CRUD Class (1-2 days)

### 5.1 Create async base CRUD

**File**: `app/crud/base.py`

The current `CRUDBase` class has methods like `get()`, `get_multi()`, `create()`, `update()`, `remove()`. Create async versions:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

class AsyncCRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, db: AsyncSession, id: Any) -> Optional[ModelType]:
        result = await db.execute(select(self.model).filter(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        result = await db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, *, db_obj: ModelType, obj_in) -> ModelType:
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: Any) -> ModelType:
        result = await db.execute(select(self.model).filter(self.model.id == id))
        obj = result.scalar_one_or_none()
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj
```

### 5.2 Key SQLAlchemy Async Differences to Remember

| Sync Pattern | Async Equivalent |
|-------------|------------------|
| `db.query(Model).filter(...)` | `await db.execute(select(Model).where(...))` then `.scalars().all()` |
| `db.query(Model).filter(...).first()` | `result = await db.execute(select(Model).where(...))` then `result.scalar_one_or_none()` |
| `db.query(func.count(...))` | `await db.execute(select(func.count(...)))` then `result.scalar()` |
| `db.query(Model).join(...)` | `await db.execute(select(Model).join(...))` |
| `db.add(obj)` | `db.add(obj)` (same - not awaited) |
| `db.commit()` | `await db.commit()` |
| `db.rollback()` | `await db.rollback()` |
| `db.refresh(obj)` | `await db.refresh(obj)` |
| `db.delete(obj)` | `await db.delete(obj)` |
| `obj.relationship_attr` (lazy load) | Must use `selectinload()` / `joinedload()` eagerly |

### 5.3 Critical: Eager Loading for Relationships

**This is the #1 gotcha in async SQLAlchemy.** Lazy loading doesn't work with async sessions because it triggers a synchronous SQL query outside the async context.

For every query that accesses relationships, you MUST add eager loading:

```python
# BEFORE (sync - lazy loading works)
event = db.query(Event).filter(Event.id == event_id).first()
venue_name = event.venue.name  # Lazy loads venue - works in sync

# AFTER (async - must eager load)
from sqlalchemy.orm import selectinload, joinedload

result = await db.execute(
    select(Event)
    .where(Event.id == event_id)
    .options(selectinload(Event.venue))  # Eager load venue
)
event = result.scalar_one_or_none()
venue_name = event.venue.name  # Already loaded - no lazy query
```

**Strategy for choosing eager loading type**:
- `selectinload()` - For one-to-many / many-to-many (fires a separate SELECT IN query). Better for collections.
- `joinedload()` - For many-to-one / one-to-one (uses JOIN). Better for single objects.
- `subqueryload()` - For complex cases where selectinload generates too many params.

---

## 6. Phase 3: CRUD Files (5-7 days)

Convert all 39 CRUD files. Prioritize by usage frequency and size.

### Conversion Order (by priority)

**Batch 1 - Core entities (Day 1-2)**:
1. `crud_event.py` (318 lines) - Used everywhere
2. `crud_registration.py` (135 lines) - Hot path for attendees
3. `crud_session.py` (96 lines) - Used in event pages
4. `crud_venue.py` (11 lines) - Quick win
5. `crud_speaker.py` (60 lines) - Quick win
6. `crud_presentation.py` (75 lines) - Quick win

**Batch 2 - Ticketing & payments (Day 2-3)**:
7. `ticket_crud.py` (377 lines) - Revenue path
8. `crud_ticket_type.py` (168 lines)
9. `crud_order.py` (301 lines)
10. `crud_payment.py` (238 lines)
11. `crud_refund.py` (163 lines)
12. `crud_offer.py` (237 lines)
13. `crud_offer_purchase.py` (197 lines)
14. `promo_code_crud.py` (223 lines)
15. `crud_promo_code.py` (183 lines)

**Batch 3 - Sponsors & ads (Day 3-4)**:
16. `crud_sponsor.py` (842 lines) - **Largest file**
17. `crud_sponsor_campaign.py` (292 lines)
18. `crud_campaign_delivery.py` (238 lines)
19. `crud_ad.py` (200 lines)
20. `crud_ad_event.py` (284 lines)
21. `crud_monetization_event.py` (322 lines)
22. `crud_ab_test.py` (196 lines)

**Batch 4 - Waitlists & analytics (Day 4-5)**:
23. `crud_session_waitlist.py` (247 lines)
24. `crud_waitlist.py` (23 lines)
25. `crud_waitlist_analytics.py` (182 lines)
26. `crud_session_capacity.py` (123 lines)
27. `crud_dashboard.py` (344 lines)
28. `crud_virtual_attendance.py` (318 lines)

**Batch 5 - Remaining (Day 5)**:
29. `crud_pre_event_email.py` (245 lines)
30. `crud_session_reminder.py` (235 lines)
31. `crud_email_preference.py` (169 lines)
32. `crud_webhook_event.py` (220 lines)
33. `crud_audit_log.py` (180 lines)
34. `crud_domain_event.py` (36 lines)
35. `crud_demo_request.py` (32 lines)
36. `crud_blueprint.py` (10 lines)
37. `ticket_type_v2.py` (226 lines)

### Conversion Pattern for Each CRUD File

```python
# BEFORE: crud_event.py
from sqlalchemy.orm import Session

class CRUDEvent(CRUDBase[Event, EventCreate, EventUpdate]):
    def get_by_organizer(self, db: Session, *, organizer_id: str) -> List[Event]:
        return db.query(Event).filter(
            Event.organizer_id == organizer_id,
            Event.is_archived == False
        ).all()

# AFTER: crud_event.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class CRUDEvent(AsyncCRUDBase[Event, EventCreate, EventUpdate]):
    async def get_by_organizer(self, db: AsyncSession, *, organizer_id: str) -> List[Event]:
        result = await db.execute(
            select(Event).where(
                Event.organizer_id == organizer_id,
                Event.is_archived == False
            )
        )
        return list(result.scalars().all())
```

---

## 7. Phase 4: API Endpoints (3-4 days)

### 29 endpoint files to convert

**Already partially async (fix DB usage - Day 1)**:
1. `webhooks.py` (410 lines, 7 async fns)
2. `analytics.py` (256 lines, 4 async fns)
3. `calendar.py` (177 lines, 2 async fns)
4. `organizations.py` (111 lines, 1 async fn)
5. `offer_webhooks.py` (188 lines, 3 async fns)
6. `sponsor_campaigns.py` (713 lines, 12 async fns)
7. `reports.py` (240 lines, 1 async fn)

**Fully sync, convert to async (Day 2-4)**:
8. `sponsors.py` (1,738 lines) - **Largest endpoint file**
9. `admin_waitlist.py` (972 lines)
10. `offers.py` (639 lines)
11. `presentations.py` (561 lines)
12. `waitlist.py` (553 lines)
13. `ab_testing.py` (448 lines)
14. `ads.py` (419 lines)
15. `events.py` (400 lines)
16. `internals.py` (324 lines)
17. `sponsor_team.py` (296 lines)
18. `email_preferences.py` (221 lines)
19. `blueprints.py` (174 lines)
20. `speakers.py` (158 lines)
21. `sessions.py` (155 lines)
22. `sponsor_user_settings.py` (133 lines)
23. `venues.py` (124 lines)
24. `registrations.py` (97 lines)
25. `sponsor_user_permissions.py` (87 lines)
26. `demo_requests.py` (66 lines)
27. `public.py` (25 lines)

### Conversion Pattern for Endpoints

```python
# BEFORE
@router.get("/events")
def list_events(db: Session = Depends(get_db), user = Depends(get_current_user)):
    events = crud.event.get_by_organizer(db, organizer_id=user.id)
    return events

# AFTER
@router.get("/events")
async def list_events(db: AsyncSession = Depends(get_async_db), user = Depends(get_current_user)):
    events = await crud.event.get_by_organizer(db, organizer_id=user.id)
    return events
```

---

## 8. Phase 5: GraphQL Layer (3-4 days)

### The Big Fix: Async Functions Already Exist, Just Need Async DB

This phase has the **highest impact** because 100+ GraphQL resolvers are already `async def` but are using sync sessions, causing the exact thread-pool bottleneck we want to eliminate.

### Files to convert:

| File | Lines | Async Fns | Priority |
|------|-------|-----------|----------|
| `mutations.py` | 1,988 | 50+ | HIGH |
| `queries.py` | 1,686 | 30+ | HIGH |
| `types.py` | 962 | ~15 | HIGH |
| `waitlist_mutations.py` | 636 | ~10 | MEDIUM |
| `payment_types.py` | 596 | ~5 | MEDIUM |
| `payment_mutations.py` | 576 | 6 | MEDIUM |
| `sponsor_mutations.py` | 531 | ~8 | MEDIUM |
| `waitlist_queries.py` | 469 | ~8 | MEDIUM |
| `sponsor_queries.py` | 437 | ~6 | MEDIUM |
| `offer_mutations.py` | 430 | 1 | MEDIUM |
| `ad_mutations.py` | 425 | ~5 | MEDIUM |
| `sponsor_types.py` | 385 | ~3 | LOW |
| `ticket_mutations.py` | 362 | 9 | MEDIUM |
| `ticket_queries.py` | 336 | 11 | MEDIUM |
| `payment_queries.py` | 301 | ~4 | MEDIUM |
| `waitlist_types.py` | 238 | ~2 | LOW |
| `ticket_types.py` | 453 | ~3 | LOW |
| `dataloaders.py` | 155 | 4 | HIGH |
| `router.py` | 56 | 1 | HIGH (context injection) |
| `schema.py` | 14 | 0 | LOW |

### GraphQL Context Update

**File**: `app/graphql/router.py`

```python
# BEFORE
async def get_context(db=Depends(get_db), ...):
    return {"db": db, "loaders": create_dataloaders(db)}

# AFTER
async def get_context(db=Depends(get_async_db), ...):
    return {"db": db, "loaders": create_async_dataloaders(db)}
```

### DataLoader Update

**File**: `app/graphql/dataloaders.py`

```python
# BEFORE
async def batch_load_venues(keys: list[str]) -> list[Venue | None]:
    venues = db.query(Venue).filter(Venue.id.in_(keys)).all()

# AFTER
async def batch_load_venues(keys: list[str]) -> list[Venue | None]:
    result = await db.execute(select(Venue).where(Venue.id.in_(keys)))
    venues = result.scalars().all()
```

---

## 9. Phase 6: Background Tasks & Services (2-3 days)

### Background Tasks (APScheduler)

| File | Lines | Notes |
|------|-------|-------|
| `session_reminder_tasks.py` | 493 | Also needs httpx → AsyncClient |
| `pre_event_email_tasks.py` | 481 | Heavy email operations |
| `offer_tasks.py` | 225 | Offer expiration checks |
| `waitlist_tasks.py` | 224 | Waitlist processing |
| `ad_tasks.py` | 142 | Ad serving logic |
| `analytics_tasks.py` | 95 | Analytics aggregation |

**APScheduler async conversion**:
```python
# BEFORE (BackgroundScheduler)
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()

# AFTER (AsyncIOScheduler)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler()
```

> **Note**: If using APScheduler 3.x, `AsyncIOScheduler` runs jobs as coroutines. If you upgrade to APScheduler 4.x, all jobs are natively async.

### Service Layer

| File | Lines | Notes |
|------|-------|-------|
| `payment_service.py` | 629 | Stripe calls (already async-compatible) |
| `ticket_service.py` | 558 | Heavy DB operations |
| `offer_reservation_service.py` | 265 | Redis + DB |
| `offer_stripe_service.py` | 244 | Stripe API calls |
| `realtime_client.py` | 242 | httpx → AsyncClient |
| `ai_message_generator.py` | 276 | External AI API calls |
| `provider_interface.py` | 233 | Abstract interface |
| `provider_factory.py` | 232 | Factory pattern |
| `offer_helpers.py` | 201 | Utility functions |

### httpx Conversion (16 calls across 5 files)

```python
# BEFORE
with httpx.Client() as client:
    response = client.post(url, json=payload, headers=headers)

# AFTER
async with httpx.AsyncClient() as client:
    response = await client.post(url, json=payload, headers=headers)
```

### Celery Tasks

**File**: `app/tasks.py` (134 lines) - `process_presentation` task

**Recommendation**: Keep Celery tasks synchronous. Celery workers run in separate processes and don't benefit from async. They process PDFs (CPU-bound), so async wouldn't help. Use the sync `SessionLocal` for Celery tasks.

---

## 10. Phase 7: Cleanup & Testing (2-3 days)

### 10.1 Remove Sync Infrastructure

Once all code is converted:

1. Remove sync `engine` from `session.py` (keep for Alembic only)
2. Remove `SessionLocal` (keep for Celery tasks only)
3. Remove `get_db()` dependency (keep for Celery tasks only)
4. Remove `CRUDBase` sync class
5. Rename `AsyncCRUDBase` → `CRUDBase`
6. Rename `get_async_db` → `get_db`

### 10.2 Model Relationship Audit

Go through every model and set appropriate lazy loading defaults:

```python
# In models, set lazy="selectin" for commonly accessed relationships
class Event(Base):
    venue = relationship("Venue", lazy="selectin")       # Always need venue
    sessions = relationship("Session", lazy="noload")     # Load explicitly when needed
    registrations = relationship("Registration", lazy="noload")  # Too many to auto-load
```

**Lazy loading options for async**:
- `lazy="selectin"` - Auto eager load (good for always-needed relationships)
- `lazy="joined"` - Auto eager load via JOIN
- `lazy="noload"` - Never auto load (must use `.options()` explicitly)
- `lazy="raise"` - Raise error if accessed without explicit loading (strictest, catches bugs)

### 10.3 Testing Strategy

1. **Unit tests**: Update all test fixtures to use `AsyncSession`
2. **Integration tests**: Test each converted endpoint with actual DB
3. **Load testing**: Compare before/after with `locust` or `k6`
   - Test with 100, 500, 1000 concurrent users
   - Measure p50, p95, p99 latencies
   - Monitor connection pool usage
4. **Regression testing**: Ensure all existing functionality works

### 10.4 Alembic Configuration

Alembic migrations should **stay synchronous**. The `env.py` file uses the sync engine:

```python
# alembic/env.py - NO CHANGES NEEDED
# Alembic uses psycopg2-binary (sync) and that's fine
# Migrations are run once, not in the hot path
```

---

## 11. File-by-File Checklist

Use this checklist to track progress. Check off each file as it's converted.

### Foundation
- [ ] `requirements.txt` - Add asyncpg
- [ ] `app/db/session.py` - Add async engine + session
- [ ] `app/api/deps.py` - Add async dependencies
- [ ] `app/main.py` - Update lifespan
- [ ] `app/crud/base.py` - Create AsyncCRUDBase

### CRUD Files (39 files)
- [ ] `app/crud/crud_event.py`
- [ ] `app/crud/crud_registration.py`
- [ ] `app/crud/crud_session.py`
- [ ] `app/crud/crud_venue.py`
- [ ] `app/crud/crud_speaker.py`
- [ ] `app/crud/crud_presentation.py`
- [ ] `app/crud/ticket_crud.py`
- [ ] `app/crud/crud_ticket_type.py`
- [ ] `app/crud/crud_order.py`
- [ ] `app/crud/crud_payment.py`
- [ ] `app/crud/crud_refund.py`
- [ ] `app/crud/crud_offer.py`
- [ ] `app/crud/crud_offer_purchase.py`
- [ ] `app/crud/promo_code_crud.py`
- [ ] `app/crud/crud_promo_code.py`
- [ ] `app/crud/crud_sponsor.py`
- [ ] `app/crud/crud_sponsor_campaign.py`
- [ ] `app/crud/crud_campaign_delivery.py`
- [ ] `app/crud/crud_ad.py`
- [ ] `app/crud/crud_ad_event.py`
- [ ] `app/crud/crud_monetization_event.py`
- [ ] `app/crud/crud_ab_test.py`
- [ ] `app/crud/crud_session_waitlist.py`
- [ ] `app/crud/crud_waitlist.py`
- [ ] `app/crud/crud_waitlist_analytics.py`
- [ ] `app/crud/crud_session_capacity.py`
- [ ] `app/crud/crud_dashboard.py`
- [ ] `app/crud/crud_virtual_attendance.py`
- [ ] `app/crud/crud_pre_event_email.py`
- [ ] `app/crud/crud_session_reminder.py`
- [ ] `app/crud/crud_email_preference.py`
- [ ] `app/crud/crud_webhook_event.py`
- [ ] `app/crud/crud_audit_log.py`
- [ ] `app/crud/crud_domain_event.py`
- [ ] `app/crud/crud_demo_request.py`
- [ ] `app/crud/crud_blueprint.py`
- [ ] `app/crud/ticket_type_v2.py`
- [ ] `app/crud/__init__.py` - Update exports

### API Endpoints (29 files)
- [ ] `app/api/v1/endpoints/events.py`
- [ ] `app/api/v1/endpoints/registrations.py`
- [ ] `app/api/v1/endpoints/sessions.py`
- [ ] `app/api/v1/endpoints/speakers.py`
- [ ] `app/api/v1/endpoints/venues.py`
- [ ] `app/api/v1/endpoints/sponsors.py`
- [ ] `app/api/v1/endpoints/sponsor_campaigns.py`
- [ ] `app/api/v1/endpoints/sponsor_team.py`
- [ ] `app/api/v1/endpoints/sponsor_user_settings.py`
- [ ] `app/api/v1/endpoints/sponsor_user_permissions.py`
- [ ] `app/api/v1/endpoints/offers.py`
- [ ] `app/api/v1/endpoints/ads.py`
- [ ] `app/api/v1/endpoints/ab_testing.py`
- [ ] `app/api/v1/endpoints/waitlist.py`
- [ ] `app/api/v1/endpoints/admin_waitlist.py`
- [ ] `app/api/v1/endpoints/presentations.py`
- [ ] `app/api/v1/endpoints/webhooks.py`
- [ ] `app/api/v1/endpoints/offer_webhooks.py`
- [ ] `app/api/v1/endpoints/analytics.py`
- [ ] `app/api/v1/endpoints/reports.py`
- [ ] `app/api/v1/endpoints/calendar.py`
- [ ] `app/api/v1/endpoints/email_preferences.py`
- [ ] `app/api/v1/endpoints/organizations.py`
- [ ] `app/api/v1/endpoints/internals.py`
- [ ] `app/api/v1/endpoints/blueprints.py`
- [ ] `app/api/v1/endpoints/demo_requests.py`
- [ ] `app/api/v1/endpoints/public.py`
- [ ] `app/api/deps.py`

### GraphQL (20 files)
- [ ] `app/graphql/router.py` - Inject async session
- [ ] `app/graphql/dataloaders.py` - Async batch loaders
- [ ] `app/graphql/types.py`
- [ ] `app/graphql/queries.py`
- [ ] `app/graphql/mutations.py`
- [ ] `app/graphql/payment_mutations.py`
- [ ] `app/graphql/payment_queries.py`
- [ ] `app/graphql/payment_types.py`
- [ ] `app/graphql/ticket_mutations.py`
- [ ] `app/graphql/ticket_queries.py`
- [ ] `app/graphql/ticket_types.py`
- [ ] `app/graphql/sponsor_mutations.py`
- [ ] `app/graphql/sponsor_queries.py`
- [ ] `app/graphql/sponsor_types.py`
- [ ] `app/graphql/offer_mutations.py`
- [ ] `app/graphql/waitlist_mutations.py`
- [ ] `app/graphql/waitlist_queries.py`
- [ ] `app/graphql/waitlist_types.py`
- [ ] `app/graphql/ad_mutations.py`
- [ ] `app/graphql/schema.py`

### Background Tasks (7 files)
- [ ] `app/scheduler.py` - Switch to AsyncIOScheduler
- [ ] `app/background_tasks/session_reminder_tasks.py`
- [ ] `app/background_tasks/pre_event_email_tasks.py`
- [ ] `app/background_tasks/offer_tasks.py`
- [ ] `app/background_tasks/waitlist_tasks.py`
- [ ] `app/background_tasks/ad_tasks.py`
- [ ] `app/background_tasks/analytics_tasks.py`

### Services (9+ files)
- [ ] `app/services/payment_service.py`
- [ ] `app/services/ticket_service.py`
- [ ] `app/services/offer_reservation_service.py`
- [ ] `app/services/offer_stripe_service.py`
- [ ] `app/services/realtime_client.py`
- [ ] `app/services/ai_message_generator.py`
- [ ] `app/services/provider_interface.py`
- [ ] `app/services/provider_factory.py`
- [ ] `app/services/offer_helpers.py`

### Utils (httpx conversion)
- [ ] `app/utils/sponsor_notifications.py` (9 httpx calls)

### Cleanup
- [ ] Remove sync engine (keep for Alembic/Celery only)
- [ ] Remove sync SessionLocal (keep for Celery only)
- [ ] Audit all model relationships for lazy loading strategy
- [ ] Load test with 1,000 concurrent users
- [ ] Update all tests

---

## 12. Key Code Transformations

### Quick Reference Card

```python
# ──────────────────────────────────────────────────────────────
# QUERIES
# ──────────────────────────────────────────────────────────────

# Get by ID
# SYNC:  db.query(Event).filter(Event.id == id).first()
# ASYNC:
result = await db.execute(select(Event).where(Event.id == id))
event = result.scalar_one_or_none()

# Get multiple with filter
# SYNC:  db.query(Event).filter(Event.organizer_id == uid).all()
# ASYNC:
result = await db.execute(select(Event).where(Event.organizer_id == uid))
events = list(result.scalars().all())

# Count
# SYNC:  db.query(func.count(Registration.id)).filter(...).scalar()
# ASYNC:
result = await db.execute(select(func.count(Registration.id)).where(...))
count = result.scalar()

# Join
# SYNC:  db.query(Event).join(Venue).filter(Venue.city == "NYC").all()
# ASYNC:
result = await db.execute(
    select(Event).join(Venue).where(Venue.city == "NYC")
)
events = list(result.scalars().all())

# Eager loading (CRITICAL for async)
result = await db.execute(
    select(Event)
    .where(Event.id == id)
    .options(
        selectinload(Event.venue),
        selectinload(Event.sessions).selectinload(Session.speakers),
    )
)

# Exists check
# SYNC:  db.query(Event).filter(...).first() is not None
# ASYNC:
result = await db.execute(select(exists().where(Event.id == id)))
event_exists = result.scalar()

# ──────────────────────────────────────────────────────────────
# MUTATIONS
# ──────────────────────────────────────────────────────────────

# Create
db.add(new_event)
await db.commit()
await db.refresh(new_event)

# Update
event.title = "New Title"
db.add(event)
await db.commit()
await db.refresh(event)

# Bulk update
# SYNC:  db.query(Registration).filter(...).update({"status": "cancelled"})
# ASYNC:
from sqlalchemy import update
await db.execute(
    update(Registration).where(...).values(status="cancelled")
)
await db.commit()

# Delete
await db.delete(event)
await db.commit()

# Bulk delete
# SYNC:  db.query(Registration).filter(...).delete()
# ASYNC:
from sqlalchemy import delete
await db.execute(delete(Registration).where(...))
await db.commit()

# ──────────────────────────────────────────────────────────────
# TRANSACTIONS
# ──────────────────────────────────────────────────────────────

# Explicit transaction
async with db.begin():
    db.add(order)
    db.add(ticket)
    # Auto-commits on exit, auto-rolls back on exception

# Manual rollback
try:
    db.add(obj)
    await db.commit()
except Exception:
    await db.rollback()
    raise
```

---

## 13. Risks & Mitigations

### Risk 1: Lazy Loading Breakage
**Risk**: Accessing un-loaded relationships raises `MissingGreenlet` error.
**Mitigation**: Search every `db.query()` call for relationship access patterns. Add `selectinload()` / `joinedload()` as needed. Set `lazy="raise"` on models during development to catch missed spots early.

### Risk 2: Connection Pool Sizing
**Risk**: Async enables way more concurrent queries, potentially overwhelming the database.
**Mitigation**: Start with `pool_size=20, max_overflow=50` (same as current). Monitor connection count at scale. Neon (your DB provider) supports connection pooling via PgBouncer — enable it if needed.

### Risk 3: Alembic Compatibility
**Risk**: Alembic doesn't support async migrations natively.
**Mitigation**: Keep `psycopg2-binary` installed. Alembic uses the sync engine only. No changes needed to migration files.

### Risk 4: Third-Party Library Compatibility
**Risk**: Some libraries may not support async (e.g., Stripe SDK is sync).
**Mitigation**: Use `asyncio.to_thread()` to wrap sync library calls:
```python
result = await asyncio.to_thread(stripe.PaymentIntent.create, amount=1000, currency="usd")
```

### Risk 5: Test Suite Breakage
**Risk**: All test fixtures using `Session` will break.
**Mitigation**: Use `pytest-asyncio` and create async test fixtures:
```python
@pytest_asyncio.fixture
async def async_db():
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()
```

---

## 14. Prerequisites

Before starting the rewrite, ensure:

1. **Python 3.10+** - Required for full async SQLAlchemy 2.0 support (you likely already have this)
2. **SQLAlchemy >= 2.0** - Check your current version: `pip show sqlalchemy`
3. **asyncpg** - Will be added to requirements
4. **pytest-asyncio** - For async test support
5. **All current tests passing** - Don't start a rewrite on a broken test suite
6. **Database connection pooling** - Verify Neon supports the connection count you'll need (async can open many more concurrent connections)

### Version Check Commands

```bash
cd event-lifecycle-service
pip show sqlalchemy    # Need >= 2.0
python --version       # Need >= 3.10
pip show fastapi       # Need >= 0.100 for best async support
```

---

## Summary

| Phase | Work | Duration | Can Deploy After? |
|-------|------|----------|-------------------|
| 1. Foundation | Async engine + session | 2-3 days | Yes (no behavior change) |
| 2. Base CRUD | Async CRUD base class | 1-2 days | Yes (additive only) |
| 3. CRUD Files | Convert 39 files | 5-7 days | Yes (per batch) |
| 4. API Endpoints | Convert 29 files | 3-4 days | Yes (per batch) |
| 5. GraphQL | Fix 20 files | 3-4 days | Yes (per batch) |
| 6. Background | Convert 16 files | 2-3 days | Yes (per batch) |
| 7. Cleanup | Remove sync, test | 2-3 days | Yes (final deploy) |
| **Total** | **~110 files** | **~3-4 weeks** | |

> **Remember**: This is an incremental migration. You can stop at any phase and still have a working system. Each phase builds on the previous one but doesn't break what's already deployed.
