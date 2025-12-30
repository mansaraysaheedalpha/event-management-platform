# Monetization Backend Requirements - FastAPI + Socket.io

## Document Overview

**Purpose**: Backend API specification for GlobalConnect monetization features (Ads, Offers/Upsells, Waitlist)
**Target Audience**: Backend developers
**Tech Stack**: FastAPI (REST/GraphQL) + Socket.io (Real-time) + PostgreSQL + Redis
**Timeline**: Aligned with 3-phase frontend rollout (12 weeks)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Next.js Frontend                         │
│  (GraphQL Client + Socket.io Client)                        │
└──────────────┬───────────────────────┬──────────────────────┘
               │                       │
               │ GraphQL/REST          │ WebSocket
               ▼                       ▼
┌──────────────────────┐    ┌─────────────────────────┐
│   FastAPI Server     │    │  Socket.io Server       │
│  (GraphQL + REST)    │    │  (Real-time events)     │
│  Port: 8000          │    │  Port: 3002             │
└──────┬───────────────┘    └────────┬────────────────┘
       │                             │
       ├─────────────────────────────┤
       │                             │
       ▼                             ▼
┌─────────────────┐          ┌──────────────┐
│   PostgreSQL    │          │    Redis     │
│  (Primary DB)   │          │  (Cache/RT)  │
└─────────────────┘          └──────────────┘
       │
       ▼
┌─────────────────┐
│  Stripe API     │
│  (Payments)     │
└─────────────────┘
```

---

## Phase 1: Core Functionality (Weeks 1-4)

### 1.1 Offers/Upsells API

#### Database Tables

```sql
-- Core Offers Table
CREATE TABLE offers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id),

  -- Basic Info
  title VARCHAR(255) NOT NULL,
  description TEXT,
  offer_type VARCHAR(50) NOT NULL CHECK (offer_type IN (
    'TICKET_UPGRADE', 'MERCHANDISE', 'EXCLUSIVE_CONTENT', 'SERVICE'
  )),

  -- Pricing
  price DECIMAL(10, 2) NOT NULL CHECK (price >= 0),
  original_price DECIMAL(10, 2) CHECK (original_price >= price),
  currency VARCHAR(3) DEFAULT 'USD',

  -- Media
  image_url TEXT,

  -- Inventory Management
  inventory_total INT CHECK (inventory_total IS NULL OR inventory_total > 0),
  inventory_sold INT DEFAULT 0 CHECK (inventory_sold >= 0),
  inventory_reserved INT DEFAULT 0 CHECK (inventory_reserved >= 0),

  -- Stripe Integration
  stripe_product_id VARCHAR(255) UNIQUE,
  stripe_price_id VARCHAR(255) UNIQUE,

  -- Targeting & Placement
  placement VARCHAR(50) NOT NULL DEFAULT 'IN_EVENT' CHECK (placement IN (
    'CHECKOUT', 'POST_PURCHASE', 'IN_EVENT', 'EMAIL'
  )),
  target_sessions UUID[] DEFAULT ARRAY[]::UUID[],
  target_ticket_tiers VARCHAR(50)[] DEFAULT ARRAY[]::VARCHAR[],

  -- Scheduling
  expires_at TIMESTAMP WITH TIME ZONE,
  starts_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Status
  is_active BOOLEAN DEFAULT true,
  is_archived BOOLEAN DEFAULT false,

  -- Metadata
  metadata JSONB DEFAULT '{}'::jsonb,

  -- Timestamps
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Constraints
  CONSTRAINT valid_inventory CHECK (
    inventory_total IS NULL OR
    (inventory_sold + inventory_reserved <= inventory_total)
  )
);

CREATE INDEX idx_offers_event_id ON offers(event_id) WHERE is_archived = false;
CREATE INDEX idx_offers_placement ON offers(placement) WHERE is_active = true;
CREATE INDEX idx_offers_expires_at ON offers(expires_at) WHERE expires_at IS NOT NULL;

-- Offer Purchases
CREATE TABLE offer_purchases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id UUID NOT NULL REFERENCES offers(id),
  user_id UUID NOT NULL REFERENCES users(id),
  order_id UUID NOT NULL REFERENCES orders(id),

  -- Purchase Details
  quantity INT NOT NULL DEFAULT 1 CHECK (quantity > 0),
  unit_price DECIMAL(10, 2) NOT NULL,
  total_price DECIMAL(10, 2) NOT NULL,
  currency VARCHAR(3) DEFAULT 'USD',

  -- Fulfillment
  fulfillment_status VARCHAR(50) DEFAULT 'PENDING' CHECK (fulfillment_status IN (
    'PENDING', 'PROCESSING', 'FULFILLED', 'FAILED', 'REFUNDED'
  )),
  fulfillment_type VARCHAR(50) CHECK (fulfillment_type IN (
    'DIGITAL', 'PHYSICAL', 'SERVICE', 'TICKET'
  )),
  digital_content_url TEXT,
  access_code VARCHAR(255),
  tracking_number VARCHAR(255),

  -- Timestamps
  purchased_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  fulfilled_at TIMESTAMP WITH TIME ZONE,
  refunded_at TIMESTAMP WITH TIME ZONE,

  CONSTRAINT valid_total_price CHECK (total_price = unit_price * quantity)
);

CREATE INDEX idx_offer_purchases_user ON offer_purchases(user_id);
CREATE INDEX idx_offer_purchases_offer ON offer_purchases(offer_id);
CREATE INDEX idx_offer_purchases_order ON offer_purchases(order_id);
CREATE INDEX idx_offer_purchases_status ON offer_purchases(fulfillment_status);
```

#### REST Endpoints

```python
# offers.py (FastAPI Router)

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from uuid import UUID

router = APIRouter(prefix="/api/v1/offers", tags=["offers"])

# ==================== DTOs ====================

class OfferCreateDTO(BaseModel):
    event_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    offer_type: str = Field(..., regex="^(TICKET_UPGRADE|MERCHANDISE|EXCLUSIVE_CONTENT|SERVICE)$")
    price: Decimal = Field(..., ge=0, decimal_places=2)
    original_price: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    currency: str = Field("USD", regex="^[A-Z]{3}$")
    image_url: Optional[str] = None
    inventory_total: Optional[int] = Field(None, gt=0)
    placement: str = Field("IN_EVENT", regex="^(CHECKOUT|POST_PURCHASE|IN_EVENT|EMAIL)$")
    target_sessions: List[UUID] = []
    target_ticket_tiers: List[str] = []
    expires_at: Optional[datetime] = None
    starts_at: Optional[datetime] = None

class OfferUpdateDTO(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    original_price: Optional[Decimal] = None
    image_url: Optional[str] = None
    inventory_total: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None

class OfferResponse(BaseModel):
    id: UUID
    event_id: UUID
    title: str
    description: Optional[str]
    offer_type: str
    price: Decimal
    original_price: Optional[Decimal]
    currency: str
    image_url: Optional[str]
    inventory: dict  # {total, available, sold, reserved}
    placement: str
    target_sessions: List[UUID]
    target_ticket_tiers: List[str]
    stripe_price_id: Optional[str]
    expires_at: Optional[datetime]
    is_active: bool
    created_at: datetime

class OfferPurchaseDTO(BaseModel):
    offer_id: UUID
    quantity: int = Field(1, gt=0, le=100)

# ==================== Endpoints ====================

@router.post("/", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
async def create_offer(
    offer_data: OfferCreateDTO,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new offer for an event.

    **Business Logic**:
    1. Validate user has permission to manage event
    2. Create Stripe Product and Price
    3. Insert offer into database
    4. Return created offer with Stripe IDs

    **Stripe Integration**:
    - Create Product: stripe.Product.create(name=title, metadata={offer_id})
    - Create Price: stripe.Price.create(product=product_id, unit_amount=price*100, currency=currency)
    """
    # TODO: Implement
    # 1. Check user permission: verify_event_access(current_user, offer_data.event_id, "ADMIN")
    # 2. Create Stripe product/price
    # 3. Insert into DB with stripe_product_id and stripe_price_id
    # 4. Return offer
    pass

@router.get("/events/{event_id}", response_model=List[OfferResponse])
async def get_event_offers(
    event_id: UUID,
    placement: Optional[str] = None,
    session_id: Optional[UUID] = None,
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all offers for an event with optional filtering.

    **Query Logic**:
    - Filter by placement (CHECKOUT, IN_EVENT, etc.)
    - Filter by session_id (offers targeting specific session)
    - Filter by active status and expiration date
    - Order by: placement priority, then created_at DESC

    **Targeting Logic**:
    If session_id provided:
      - Include offers where target_sessions is empty (show to all)
      - Include offers where session_id IN target_sessions

    **Availability Calculation**:
    available = inventory_total - inventory_sold - inventory_reserved
    """
    pass

@router.get("/events/{event_id}/active", response_model=List[OfferResponse])
async def get_active_offers_for_attendee(
    event_id: UUID,
    session_id: Optional[UUID] = None,
    placement: str = "IN_EVENT",
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    PUBLIC endpoint: Get active offers that should be shown to an attendee.

    **Filtering**:
    1. is_active = true AND is_archived = false
    2. NOW() BETWEEN starts_at AND (expires_at OR infinity)
    3. inventory_available > 0 (if inventory tracking enabled)
    4. placement = <requested_placement>
    5. Targeting rules match (session, ticket tier if user authenticated)

    **Personalization** (if user authenticated):
    - Check user's ticket tier
    - Filter by target_ticket_tiers if specified
    - Exclude already purchased offers (optional)
    """
    pass

@router.post("/purchase", status_code=status.HTTP_200_OK)
async def purchase_offer(
    purchase_data: OfferPurchaseDTO,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add offer to cart / create checkout session with offer.

    **Flow**:
    1. Validate offer is available (inventory check)
    2. Reserve inventory (increment inventory_reserved)
    3. Create or update checkout session
    4. Add offer as line item to Stripe checkout
    5. Return checkout URL

    **Inventory Reservation**:
    - Use Redis for temporary reservation with TTL (15 minutes)
    - Key: offer_reservation:{checkout_session_id}:{offer_id}
    - On checkout complete: move reserved → sold
    - On checkout expire: release reserved inventory

    **Response**:
    {
      "checkout_session_id": "cs_xxx",
      "stripe_checkout_url": "https://checkout.stripe.com/...",
      "order": { ... }
    }
    """
    pass

@router.get("/my-purchases/{event_id}", response_model=List[dict])
async def get_my_purchased_offers(
    event_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all offers purchased by current user for an event.

    **Query**:
    SELECT op.*, o.* FROM offer_purchases op
    JOIN offers o ON op.offer_id = o.id
    WHERE op.user_id = {current_user.id} AND o.event_id = {event_id}
    ORDER BY op.purchased_at DESC

    **Response includes**:
    - Offer details
    - Purchase details (quantity, price, date)
    - Fulfillment status
    - Digital content access (if applicable)
    """
    pass

@router.patch("/{offer_id}", response_model=OfferResponse)
async def update_offer(
    offer_id: UUID,
    update_data: OfferUpdateDTO,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update an existing offer.

    **Validation**:
    - Cannot change price if offer has purchases (create new offer instead)
    - If changing inventory_total, ensure >= (inventory_sold + inventory_reserved)
    - Update Stripe Price if price changed
    """
    pass

@router.delete("/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_offer(
    offer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Soft delete (archive) an offer.
    Set is_archived = true, is_active = false
    """
    pass

# ==================== Background Tasks ====================

async def release_expired_reservations():
    """
    Cron job: Run every 5 minutes

    Find all expired checkout sessions and release their inventory reservations.

    Steps:
    1. Query Redis for keys matching offer_reservation:*
    2. For expired keys (TTL = 0), decrement inventory_reserved
    3. Delete Redis key
    """
    pass

async def auto_expire_offers():
    """
    Cron job: Run every hour

    Set is_active = false for offers where NOW() > expires_at
    """
    pass
```

#### GraphQL Schema (if using Strawberry/Graphene)

```python
# schema.py

import strawberry
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

@strawberry.type
class InventoryStatus:
    total: Optional[int]
    available: int
    sold: int
    reserved: int

@strawberry.type
class Offer:
    id: strawberry.ID
    event_id: strawberry.ID
    title: str
    description: Optional[str]
    offer_type: str
    price: Decimal
    original_price: Optional[Decimal]
    currency: str
    image_url: Optional[str]
    inventory: InventoryStatus
    placement: str
    target_sessions: List[strawberry.ID]
    stripe_price_id: Optional[str]
    expires_at: Optional[datetime]
    is_active: bool

@strawberry.type
class Query:
    @strawberry.field
    async def event_offers(
        self,
        event_id: strawberry.ID,
        placement: Optional[str] = None
    ) -> List[Offer]:
        # Implementation
        pass

    @strawberry.field
    async def active_offers(
        self,
        event_id: strawberry.ID,
        session_id: Optional[strawberry.ID] = None,
        placement: str = "IN_EVENT"
    ) -> List[Offer]:
        # Implementation
        pass

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_offer(self, input: OfferCreateInput) -> Offer:
        # Implementation
        pass

    @strawberry.mutation
    async def purchase_offer(self, offer_id: strawberry.ID, quantity: int = 1) -> PurchaseResult:
        # Implementation
        pass
```

---

### 1.2 Advertisements API

#### Database Tables

```sql
-- Ads Table
CREATE TABLE ads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id),

  -- Ad Details
  name VARCHAR(255) NOT NULL,  -- Internal name for organizers
  content_type VARCHAR(50) NOT NULL CHECK (content_type IN (
    'BANNER', 'VIDEO', 'SPONSORED_SESSION', 'INTERSTITIAL'
  )),
  media_url TEXT NOT NULL,
  click_url TEXT NOT NULL,

  -- Display Settings
  display_duration_seconds INT DEFAULT 30 CHECK (display_duration_seconds > 0),
  aspect_ratio VARCHAR(20) DEFAULT '16:9',  -- For responsive sizing

  -- Scheduling
  starts_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  ends_at TIMESTAMP WITH TIME ZONE,

  -- Targeting
  placements VARCHAR(50)[] DEFAULT ARRAY['EVENT_HERO']::VARCHAR[],
  target_sessions UUID[] DEFAULT ARRAY[]::UUID[],

  -- Rotation & Frequency
  weight INT DEFAULT 1 CHECK (weight > 0),  -- Higher weight = shown more
  frequency_cap INT DEFAULT 3,  -- Max impressions per user per session

  -- Status
  is_active BOOLEAN DEFAULT true,
  is_archived BOOLEAN DEFAULT false,

  -- Metadata
  metadata JSONB DEFAULT '{}'::jsonb,

  -- Timestamps
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_ads_event_active ON ads(event_id) WHERE is_active = true AND is_archived = false;
CREATE INDEX idx_ads_schedule ON ads(starts_at, ends_at) WHERE is_active = true;

-- Ad Events (Impressions & Clicks)
CREATE TABLE ad_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ad_id UUID NOT NULL REFERENCES ads(id),
  user_id UUID REFERENCES users(id),  -- Nullable for anonymous
  session_id TEXT,  -- Browser session ID for anonymous tracking

  -- Event Details
  event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('IMPRESSION', 'CLICK')),
  context VARCHAR(255),  -- Page URL or session ID where ad shown

  -- Viewability Metrics (for impressions)
  viewable_duration_ms INT,  -- How long ad was visible
  viewport_percentage INT,  -- % of ad visible (0-100)

  -- Technical Data
  user_agent TEXT,
  ip_address INET,
  referer TEXT,

  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_ad_events_ad_type ON ad_events(ad_id, event_type);
CREATE INDEX idx_ad_events_created ON ad_events(created_at);
PARTITION BY RANGE (created_at);  -- Partition by month for performance

-- Ad Analytics Aggregated (Materialized View updated hourly)
CREATE MATERIALIZED VIEW ad_analytics_daily AS
SELECT
  ad_id,
  DATE(created_at) as date,
  COUNT(*) FILTER (WHERE event_type = 'IMPRESSION') as impressions,
  COUNT(*) FILTER (WHERE event_type = 'IMPRESSION' AND viewport_percentage >= 50 AND viewable_duration_ms >= 1000) as viewable_impressions,
  COUNT(*) FILTER (WHERE event_type = 'CLICK') as clicks,
  COUNT(DISTINCT COALESCE(user_id::text, session_id)) as unique_users,
  ROUND(
    COUNT(*) FILTER (WHERE event_type = 'CLICK')::decimal /
    NULLIF(COUNT(*) FILTER (WHERE event_type = 'IMPRESSION'), 0) * 100,
    4
  ) as ctr_percentage
FROM ad_events
GROUP BY ad_id, DATE(created_at);

CREATE UNIQUE INDEX idx_ad_analytics_daily_unique ON ad_analytics_daily(ad_id, date);

-- Refresh schedule: Run every hour
-- REFRESH MATERIALIZED VIEW CONCURRENTLY ad_analytics_daily;
```

#### REST Endpoints

```python
# ads.py

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID

router = APIRouter(prefix="/api/v1/ads", tags=["ads"])

# ==================== DTOs ====================

class AdCreateDTO(BaseModel):
    event_id: UUID
    name: str
    content_type: str
    media_url: str
    click_url: str
    display_duration_seconds: int = 30
    placements: List[str] = ["EVENT_HERO"]
    target_sessions: List[UUID] = []
    weight: int = 1
    frequency_cap: int = 3
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None

class AdResponse(BaseModel):
    id: UUID
    event_id: UUID
    name: str
    content_type: str
    media_url: str
    click_url: str
    display_duration_seconds: int
    placements: List[str]
    weight: int
    frequency_cap: int
    is_active: bool
    analytics: Optional[dict] = None  # {impressions, clicks, ctr}

class ImpressionTrackingDTO(BaseModel):
    ad_id: UUID
    context: Optional[str] = None
    viewable_duration_ms: int
    viewport_percentage: int

class BatchImpressionDTO(BaseModel):
    impressions: List[ImpressionTrackingDTO]

# ==================== Endpoints ====================

@router.post("/", response_model=AdResponse, status_code=201)
async def create_ad(
    ad_data: AdCreateDTO,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create new advertisement.

    **Validations**:
    - media_url must be valid URL (check format)
    - click_url must be valid URL
    - content_type must be BANNER|VIDEO|SPONSORED_SESSION|INTERSTITIAL
    - placements must be valid (EVENT_HERO, SESSION_LIST, SIDEBAR, etc.)
    """
    pass

@router.get("/serve", response_model=List[AdResponse])
async def serve_ads(
    event_id: UUID,
    placement: str,
    session_id: Optional[UUID] = None,
    limit: int = 3,
    session_token: Optional[str] = None,  # Browser session for frequency capping
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Serve ads to attendee based on context and frequency capping.

    **Ad Selection Algorithm**:
    1. Filter by: is_active=true, NOW() BETWEEN starts_at AND ends_at, placement match
    2. Filter by targeting: session_id if specified
    3. Apply frequency capping: check Redis for user/session impression count
    4. Weighted random selection: ads with higher weight more likely
    5. Return up to {limit} ads

    **Frequency Capping (Redis)**:
    - Key: ad_frequency:{session_token}:{ad_id}
    - Value: impression count
    - TTL: 1 hour
    - If count >= frequency_cap, exclude ad from selection

    **Weighted Random**:
    ```python
    import random
    weights = [ad.weight for ad in eligible_ads]
    selected = random.choices(eligible_ads, weights=weights, k=limit)
    ```
    """
    pass

@router.post("/track/impressions", status_code=202)
async def track_impressions(
    batch: BatchImpressionDTO,
    session_token: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Bulk track ad impressions (async processing).

    **Processing**:
    1. Validate all ad_ids exist
    2. Filter viewable impressions (viewport >= 50% AND duration >= 1000ms)
    3. Batch insert to ad_events table
    4. Update Redis frequency counters
    5. Queue for real-time analytics update (optional)

    **Viewability Standard** (IAB):
    - Display ads: 50% of pixels visible for 1+ second
    - Video ads: 50% of pixels visible for 2+ seconds

    **Response**: 202 Accepted (async processing)
    """
    pass

@router.post("/track/click/{ad_id}", status_code=200)
async def track_click(
    ad_id: UUID,
    context: Optional[str] = None,
    session_token: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Track ad click and return click_url for redirect.

    **Processing**:
    1. Insert click event to ad_events
    2. Return ad's click_url for client-side redirect

    **Response**:
    {
      "redirect_url": "https://sponsor-site.com/promo",
      "open_in_new_tab": true
    }
    """
    pass

@router.get("/{ad_id}/analytics")
async def get_ad_analytics(
    ad_id: UUID,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get analytics for specific ad.

    **Metrics**:
    - Total impressions
    - Viewable impressions (IAB standard)
    - Total clicks
    - CTR (click-through rate)
    - Unique users reached
    - Breakdown by day

    **Query ad_analytics_daily materialized view**
    """
    pass

@router.get("/events/{event_id}/analytics")
async def get_event_ad_analytics(
    event_id: UUID,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Aggregate analytics for all ads in an event.

    **Response**:
    {
      "total_impressions": 15420,
      "total_clicks": 234,
      "average_ctr": 1.52,
      "top_performers": [
        {"ad_id": "...", "name": "Sponsor X", "impressions": 5000, "ctr": 2.1},
        ...
      ],
      "by_placement": {
        "EVENT_HERO": {"impressions": 8000, "clicks": 150},
        "SIDEBAR": {"impressions": 7420, "clicks": 84}
      }
    }
    """
    pass
```

---

### 1.3 Waitlist Real-time System (Socket.io)

#### Database Tables

```sql
-- Session Waitlist
CREATE TABLE session_waitlist (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),

  -- Queue Management
  priority_tier VARCHAR(20) DEFAULT 'STANDARD' CHECK (priority_tier IN (
    'STANDARD', 'VIP', 'PREMIUM'
  )),
  position INT NOT NULL,  -- Position in queue (recalculated on changes)

  -- Status
  status VARCHAR(20) DEFAULT 'WAITING' CHECK (status IN (
    'WAITING', 'OFFERED', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'LEFT'
  )),

  -- Offer Details
  offer_token VARCHAR(512),  -- JWT token for claiming spot
  offer_sent_at TIMESTAMP WITH TIME ZONE,
  offer_expires_at TIMESTAMP WITH TIME ZONE,
  offer_responded_at TIMESTAMP WITH TIME ZONE,

  -- Timestamps
  joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  left_at TIMESTAMP WITH TIME ZONE,

  CONSTRAINT unique_session_user UNIQUE(session_id, user_id)
);

CREATE INDEX idx_waitlist_session_status ON session_waitlist(session_id, status);
CREATE INDEX idx_waitlist_position ON session_waitlist(session_id, priority_tier, position);
CREATE INDEX idx_waitlist_offer_expires ON session_waitlist(offer_expires_at)
  WHERE status = 'OFFERED' AND offer_expires_at IS NOT NULL;

-- Waitlist Events Log
CREATE TABLE waitlist_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  waitlist_entry_id UUID NOT NULL REFERENCES session_waitlist(id),
  event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
    'JOINED', 'POSITION_CHANGED', 'OFFERED', 'ACCEPTED',
    'DECLINED', 'EXPIRED', 'LEFT', 'REMOVED'
  )),
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_waitlist_events_entry ON waitlist_events(waitlist_entry_id);
CREATE INDEX idx_waitlist_events_type ON waitlist_events(event_type, created_at);
```

#### Redis Data Structures

```python
# Waitlist Queues (Sorted Sets - score = timestamp joined)
# Multiple queues per session for different priority tiers

# Standard tier queue
ZADD waitlist:session:{session_id}:standard {timestamp_ms} {user_id}

# VIP tier queue (processed first)
ZADD waitlist:session:{session_id}:vip {timestamp_ms} {user_id}

# Premium tier queue
ZADD waitlist:session:{session_id}:premium {timestamp_ms} {user_id}

# User metadata (Hash)
HSET waitlist:user:{user_id}:session:{session_id} status "WAITING"
HSET waitlist:user:{user_id}:session:{session_id} joined_at {timestamp}
HSET waitlist:user:{user_id}:session:{session_id} priority_tier "STANDARD"

# Offer timeout tracker (String with TTL)
SETEX waitlist:offer:{offer_token} 300 {json_data}  # 5 minutes TTL
```

#### REST Endpoints

```python
# waitlist.py

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel
from uuid import UUID
import jwt
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/sessions/{session_id}/waitlist", tags=["waitlist"])

# ==================== DTOs ====================

class WaitlistPositionResponse(BaseModel):
    position: int
    total: int
    estimated_wait_minutes: Optional[int]
    priority_tier: str

class WaitlistJoinResponse(BaseModel):
    id: UUID
    position: int
    total: int
    message: str

# ==================== Endpoints ====================

@router.post("/", response_model=WaitlistJoinResponse, status_code=201)
async def join_waitlist(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Join session waitlist.

    **Business Logic**:
    1. Check if session is at capacity (if not, can't join waitlist)
    2. Check if user already in waitlist
    3. Determine priority tier based on ticket type
    4. Add to appropriate Redis queue
    5. Calculate position
    6. Insert to DB
    7. Emit socket event to user

    **Priority Tier Logic**:
    - VIP ticket holders → VIP tier
    - Premium ticket holders → PREMIUM tier
    - Others → STANDARD tier

    **Errors**:
    - 409 if already on waitlist
    - 400 if session not full
    - 403 if user not registered for event
    """
    # Determine priority tier
    user_ticket_tier = get_user_ticket_tier(current_user.id, session_id)
    priority_tier = map_ticket_to_priority(user_ticket_tier)

    # Add to Redis queue
    timestamp = int(datetime.now().timestamp() * 1000)
    redis.zadd(f"waitlist:session:{session_id}:{priority_tier.lower()}", {current_user.id: timestamp})

    # Calculate position across all tiers
    position = calculate_waitlist_position(session_id, current_user.id, priority_tier, redis)

    # Insert to DB
    entry = db.execute("""
        INSERT INTO session_waitlist (session_id, user_id, priority_tier, position, status)
        VALUES (%s, %s, %s, %s, 'WAITING')
        RETURNING id
    """, (session_id, current_user.id, priority_tier, position))

    # Log event
    log_waitlist_event(entry.id, 'JOINED', db)

    return {
        "id": entry.id,
        "position": position,
        "total": get_total_waiting(session_id, redis),
        "message": f"You're #{position} in line"
    }

@router.delete("/", status_code=204)
async def leave_waitlist(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Leave waitlist voluntarily.

    **Process**:
    1. Remove from Redis queue
    2. Update status to 'LEFT' in DB
    3. Recalculate positions for users behind
    4. Emit position updates to affected users
    """
    # Get user's tier
    entry = db.query(SessionWaitlist).filter(
        session_id=session_id, user_id=current_user.id, status='WAITING'
    ).first()

    if not entry:
        raise HTTPException(404, "Not on waitlist")

    # Remove from Redis
    redis.zrem(f"waitlist:session:{session_id}:{entry.priority_tier.lower()}", current_user.id)

    # Update DB
    entry.status = 'LEFT'
    entry.left_at = datetime.now()
    db.commit()

    # Recalculate and notify others
    await recalculate_positions_and_notify(session_id, entry.priority_tier, redis)

@router.get("/position", response_model=WaitlistPositionResponse)
async def get_position(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Get current waitlist position.

    **Response includes**:
    - Current position
    - Total waiting
    - Estimated wait time (based on historical conversion rate)
    """
    entry = db.query(SessionWaitlist).filter(
        session_id=session_id, user_id=current_user.id
    ).first()

    if not entry or entry.status not in ['WAITING', 'OFFERED']:
        raise HTTPException(404, "Not on waitlist")

    position = calculate_waitlist_position(session_id, current_user.id, entry.priority_tier, redis)
    total = get_total_waiting(session_id, redis)
    estimated_wait = estimate_wait_time(session_id, position, db)

    return {
        "position": position,
        "total": total,
        "estimated_wait_minutes": estimated_wait,
        "priority_tier": entry.priority_tier
    }

@router.post("/accept-offer", status_code=200)
async def accept_offer(
    session_id: UUID,
    join_token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Accept waitlist offer using short-lived JWT token.

    **JWT Validation**:
    - Verify signature
    - Check expiration (5 minute window)
    - Verify user_id matches
    - Verify session_id matches
    - Verify token hasn't been used

    **Process**:
    1. Validate JWT
    2. Check if spot still available
    3. Register user for session
    4. Update waitlist entry to 'ACCEPTED'
    5. Remove from Redis queue
    6. Offer next person in line
    """
    try:
        payload = jwt.decode(join_token, JWT_SECRET, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "Offer expired")
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Invalid token")

    # Validate payload
    if payload['user_id'] != str(current_user.id) or payload['session_id'] != str(session_id):
        raise HTTPException(403, "Token not valid for this user/session")

    # Check if already used (idempotency)
    if redis.exists(f"waitlist:offer:used:{join_token}"):
        raise HTTPException(409, "Offer already accepted")

    # Register user for session
    session_registration = register_user_for_session(current_user.id, session_id, db)

    # Update waitlist
    entry = db.query(SessionWaitlist).filter(
        session_id=session_id, user_id=current_user.id, status='OFFERED'
    ).first()
    entry.status = 'ACCEPTED'
    entry.offer_responded_at = datetime.now()
    db.commit()

    # Mark token as used
    redis.setex(f"waitlist:offer:used:{join_token}", 3600, "1")

    # Remove from queue
    redis.zrem(f"waitlist:session:{session_id}:{entry.priority_tier.lower()}", current_user.id)

    # Offer to next person
    await offer_next_spot(session_id, db, redis)

    return {"success": True, "message": "Successfully joined session"}
```

#### Socket.io Events

```python
# socketio_waitlist.py

from socketio import AsyncServer
import jwt
from datetime import datetime, timedelta

sio = AsyncServer(async_mode='asgi', cors_allowed_origins='*')

# ==================== Server → Client Events ====================

async def emit_position_update(user_id: str, session_id: str, position: int, total: int):
    """
    Notify user of position change in queue.

    Event: WAITLIST_POSITION_UPDATE
    """
    room = f"user:{user_id}"
    await sio.emit('WAITLIST_POSITION_UPDATE', {
        'session_id': session_id,
        'position': position,
        'total': total,
        'estimated_wait_minutes': estimate_wait_time(session_id, position)
    }, room=room)

async def offer_spot(user_id: str, session_id: str, db: Session):
    """
    Offer waitlist spot to user with 5-minute timer.

    Event: WAITLIST_OFFER
    """
    # Generate short-lived JWT (5 minutes)
    expires_at = datetime.now() + timedelta(minutes=5)
    token = jwt.encode({
        'user_id': user_id,
        'session_id': session_id,
        'exp': expires_at
    }, JWT_SECRET, algorithm='HS256')

    # Update DB
    db.execute("""
        UPDATE session_waitlist
        SET status = 'OFFERED', offer_token = %s,
            offer_sent_at = NOW(), offer_expires_at = %s
        WHERE session_id = %s AND user_id = %s
    """, (token, expires_at, session_id, user_id))
    db.commit()

    # Emit offer
    room = f"user:{user_id}"
    await sio.emit('WAITLIST_OFFER', {
        'title': '🎉 Spot Available!',
        'message': 'A spot just opened up in the session. Accept within 5 minutes!',
        'join_token': token,
        'expires_at': expires_at.isoformat(),
        'session_id': session_id
    }, room=room)

    # Schedule expiration check
    schedule_offer_expiration_check(token, expires_at, session_id, user_id)

async def notify_offer_expired(user_id: str, session_id: str):
    """
    Notify user their offer expired.

    Event: WAITLIST_OFFER_EXPIRED
    """
    room = f"user:{user_id}"
    await sio.emit('WAITLIST_OFFER_EXPIRED', {
        'message': 'Your spot offer expired. You remain on the waitlist.',
        'session_id': session_id
    }, room=room)

# ==================== Background Tasks ====================

async def offer_next_spot(session_id: str, db: Session, redis: Redis):
    """
    Called when spot becomes available (someone leaves or offer expires).

    Logic:
    1. Check if session still has capacity
    2. Get next user from highest priority queue (VIP → PREMIUM → STANDARD)
    3. Offer spot to that user
    """
    # Check VIP queue first
    next_user = redis.zrange(f"waitlist:session:{session_id}:vip", 0, 0)
    if not next_user:
        # Try PREMIUM
        next_user = redis.zrange(f"waitlist:session:{session_id}:premium", 0, 0)
    if not next_user:
        # Try STANDARD
        next_user = redis.zrange(f"waitlist:session:{session_id}:standard", 0, 0)

    if next_user:
        user_id = next_user[0]
        await offer_spot(user_id, session_id, db)

async def check_expired_offers():
    """
    Cron job: Run every minute.

    Find offers where offer_expires_at < NOW() and status = 'OFFERED'.
    Mark as EXPIRED and offer to next person.
    """
    db = get_db()
    redis = get_redis()

    expired = db.query(SessionWaitlist).filter(
        SessionWaitlist.status == 'OFFERED',
        SessionWaitlist.offer_expires_at < datetime.now()
    ).all()

    for entry in expired:
        # Mark as expired
        entry.status = 'EXPIRED'
        db.commit()

        # Notify user
        await notify_offer_expired(entry.user_id, entry.session_id)

        # Offer to next person
        await offer_next_spot(entry.session_id, db, redis)

# ==================== Utility Functions ====================

def calculate_waitlist_position(session_id: str, user_id: str, priority_tier: str, redis: Redis) -> int:
    """
    Calculate user's position across all priority tiers.

    Logic:
    - VIP tier users are always ahead of PREMIUM/STANDARD
    - PREMIUM ahead of STANDARD
    - Within tier, ordered by join timestamp
    """
    position = 0

    # Count all users in higher priority tiers
    if priority_tier == 'PREMIUM':
        position += redis.zcard(f"waitlist:session:{session_id}:vip")
    elif priority_tier == 'STANDARD':
        position += redis.zcard(f"waitlist:session:{session_id}:vip")
        position += redis.zcard(f"waitlist:session:{session_id}:premium")

    # Count users ahead in same tier
    user_rank = redis.zrank(f"waitlist:session:{session_id}:{priority_tier.lower()}", user_id)
    if user_rank is not None:
        position += user_rank + 1  # zrank is 0-indexed

    return position

def estimate_wait_time(session_id: str, position: int, db: Session) -> int:
    """
    Estimate wait time in minutes based on historical data.

    Logic:
    - Calculate average time between acceptances for this session/event
    - Multiply by position
    - Round to nearest 5 minutes
    """
    # Query historical acceptance rate
    avg_time_between_acceptances = db.execute("""
        SELECT AVG(
            EXTRACT(EPOCH FROM (offer_responded_at - offer_sent_at))
        ) as avg_seconds
        FROM session_waitlist
        WHERE session_id = %s AND status = 'ACCEPTED'
        LIMIT 100
    """, (session_id,)).scalar()

    if not avg_time_between_acceptances:
        # Default: assume 1 spot every 10 minutes
        avg_time_between_acceptances = 600

    estimated_seconds = position * avg_time_between_acceptances
    estimated_minutes = int(estimated_seconds / 60)

    # Round to nearest 5
    return round(estimated_minutes / 5) * 5
```

---

## Phase 2: Analytics & Measurement (Weeks 5-7)

### 2.1 Analytics Event Tracking

#### Database Schema

```sql
-- Universal monetization events table
CREATE TABLE monetization_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id UUID NOT NULL REFERENCES events(id),
  user_id UUID REFERENCES users(id),
  session_token VARCHAR(255),  -- For anonymous users

  -- Event Classification
  event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
    -- Offer events
    'OFFER_VIEW', 'OFFER_CLICK', 'OFFER_ADD_TO_CART', 'OFFER_PURCHASE', 'OFFER_REFUND',
    -- Ad events
    'AD_IMPRESSION', 'AD_VIEWABLE_IMPRESSION', 'AD_CLICK',
    -- Waitlist events
    'WAITLIST_JOIN', 'WAITLIST_OFFER_SENT', 'WAITLIST_OFFER_ACCEPTED',
    'WAITLIST_OFFER_DECLINED', 'WAITLIST_OFFER_EXPIRED'
  )),
  entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('OFFER', 'AD', 'WAITLIST')),
  entity_id UUID NOT NULL,

  -- Revenue Attribution
  revenue_cents INT DEFAULT 0,  -- Revenue in cents (0 for non-purchase events)
  currency VARCHAR(3) DEFAULT 'USD',

  -- Context
  context JSONB DEFAULT '{}'::jsonb,  -- Flexible: {placement, session_id, referrer, etc.}

  -- Technical
  user_agent TEXT,
  ip_address INET,

  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_monetization_events_type ON monetization_events(event_type, created_at);
CREATE INDEX idx_monetization_events_entity ON monetization_events(entity_type, entity_id);
CREATE INDEX idx_monetization_events_user ON monetization_events(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_monetization_events_event ON monetization_events(event_id);

-- Partition by month for performance
ALTER TABLE monetization_events PARTITION BY RANGE (created_at);

-- Conversion funnel materialized view
CREATE MATERIALIZED VIEW monetization_conversion_funnels AS
WITH offer_funnel AS (
  SELECT
    entity_id as offer_id,
    COUNT(*) FILTER (WHERE event_type = 'OFFER_VIEW') as views,
    COUNT(*) FILTER (WHERE event_type = 'OFFER_CLICK') as clicks,
    COUNT(*) FILTER (WHERE event_type = 'OFFER_ADD_TO_CART') as add_to_cart,
    COUNT(*) FILTER (WHERE event_type = 'OFFER_PURCHASE') as purchases,
    SUM(revenue_cents) FILTER (WHERE event_type = 'OFFER_PURCHASE') as revenue_cents
  FROM monetization_events
  WHERE entity_type = 'OFFER'
  GROUP BY entity_id
)
SELECT
  offer_id,
  views,
  clicks,
  add_to_cart,
  purchases,
  revenue_cents,
  ROUND((clicks::decimal / NULLIF(views, 0)) * 100, 2) as view_to_click_rate,
  ROUND((add_to_cart::decimal / NULLIF(clicks, 0)) * 100, 2) as click_to_cart_rate,
  ROUND((purchases::decimal / NULLIF(add_to_cart, 0)) * 100, 2) as cart_to_purchase_rate,
  ROUND((purchases::decimal / NULLIF(views, 0)) * 100, 2) as overall_conversion_rate
FROM offer_funnel;
```

#### Tracking Endpoint

```python
# analytics.py

from fastapi import APIRouter, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

class EventTrackingDTO(BaseModel):
    event_type: str
    entity_type: str  # OFFER, AD, WAITLIST
    entity_id: UUID
    revenue_cents: Optional[int] = 0
    context: Optional[dict] = {}

class BatchTrackingDTO(BaseModel):
    events: List[EventTrackingDTO]

@router.post("/track", status_code=202)
async def track_events(
    batch: BatchTrackingDTO,
    background_tasks: BackgroundTasks,
    session_token: str,
    current_user: Optional[User] = Depends(get_optional_user),
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Bulk event tracking endpoint.

    **Processing** (async via background task):
    1. Extract user_agent, IP from request
    2. Batch insert to monetization_events
    3. Update real-time counters in Redis

    **Client Usage**:
    - Buffer events client-side
    - Send batch every 10 events or 30 seconds (whichever first)
    - Include session_token for anonymous tracking
    """
    user_agent = request.headers.get('user-agent')
    ip_address = request.client.host

    # Queue for async processing
    background_tasks.add_task(
        process_tracking_batch,
        events=batch.events,
        user_id=current_user.id if current_user else None,
        session_token=session_token,
        user_agent=user_agent,
        ip_address=ip_address,
        db=db
    )

    return {"status": "accepted", "queued": len(batch.events)}

async def process_tracking_batch(
    events: List[EventTrackingDTO],
    user_id: Optional[UUID],
    session_token: str,
    user_agent: str,
    ip_address: str,
    db: Session
):
    """Background task to insert events."""
    records = [
        {
            'event_type': e.event_type,
            'entity_type': e.entity_type,
            'entity_id': e.entity_id,
            'user_id': user_id,
            'session_token': session_token,
            'revenue_cents': e.revenue_cents,
            'context': e.context,
            'user_agent': user_agent,
            'ip_address': ip_address
        }
        for e in events
    ]

    db.bulk_insert_mappings(MonetizationEvent, records)
    db.commit()

@router.get("/events/{event_id}/monetization")
async def get_monetization_analytics(
    event_id: UUID,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive monetization analytics for an event.

    **Response Structure**:
    {
      "revenue": {
        "total_cents": 125000,
        "from_offers": 95000,
        "by_day": [{"date": "2025-01-01", "amount": 15000}, ...]
      },
      "offers": {
        "total_views": 15420,
        "total_purchases": 234,
        "conversion_rate": 1.52,
        "top_performers": [...]
      },
      "ads": {
        "total_impressions": 50000,
        "viewable_impressions": 35000,
        "total_clicks": 750,
        "average_ctr": 1.5
      },
      "waitlist": {
        "total_joins": 450,
        "offers_sent": 120,
        "offers_accepted": 72,
        "acceptance_rate": 60.0
      }
    }
    """
    pass
```

---

### 2.2 Reporting & Exports

```python
# reports.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import pandas as pd
from io import BytesIO

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

@router.get("/events/{event_id}/monetization/export")
async def export_monetization_report(
    event_id: UUID,
    format: str = "csv",  # csv, excel, pdf
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export monetization report in various formats.

    **CSV/Excel**: Tabular data with multiple sheets (offers, ads, waitlist)
    **PDF**: Formatted report with charts and tables
    """
    # Fetch data
    data = fetch_monetization_data(event_id, date_from, date_to, db)

    if format == "csv":
        # Convert to CSV
        df = pd.DataFrame(data['offers'])
        output = BytesIO()
        df.to_csv(output, index=False)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=monetization_{event_id}.csv"}
        )

    elif format == "excel":
        # Multiple sheets
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame(data['offers']).to_excel(writer, sheet_name='Offers', index=False)
            pd.DataFrame(data['ads']).to_excel(writer, sheet_name='Ads', index=False)
            pd.DataFrame(data['waitlist']).to_excel(writer, sheet_name='Waitlist', index=False)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=monetization_{event_id}.xlsx"}
        )

    elif format == "pdf":
        # Generate PDF report (use reportlab or weasyprint)
        pdf_content = generate_pdf_report(data)
        return StreamingResponse(
            BytesIO(pdf_content),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=monetization_{event_id}.pdf"}
        )
```

---

## Phase 3: Advanced Features (Weeks 8-12)

### 3.1 Targeting & Segmentation

```sql
-- Audience Segments
CREATE TABLE audience_segments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  name VARCHAR(255) NOT NULL,
  description TEXT,

  -- Targeting Criteria (JSON)
  criteria JSONB NOT NULL,  -- Flexible rule engine

  -- Examples:
  -- {"ticket_tiers": ["VIP", "PREMIUM"]}
  -- {"sessions_attended": {"min": 3}}
  -- {"engagement_score": {"min": 75}}
  -- {"location": {"countries": ["US", "CA"]}}

  -- Stats
  estimated_size INT DEFAULT 0,  -- Cached count
  last_calculated_at TIMESTAMP WITH TIME ZONE,

  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Link offers to segments
ALTER TABLE offers ADD COLUMN target_segments UUID[];
CREATE INDEX idx_offers_segments ON offers USING GIN(target_segments);
```

```python
# targeting.py

async def evaluate_user_matches_criteria(user: User, criteria: dict, db: Session) -> bool:
    """
    Evaluate if user matches targeting criteria.

    **Supported Criteria**:
    - ticket_tiers: ["VIP", "PREMIUM"]
    - sessions_attended: {min: 3, max: 10}
    - engagement_score: {min: 50}
    - location: {countries: ["US"]}
    - previous_purchases: {min_amount: 100}
    - registration_date: {before: "2025-01-01", after: "2024-12-01"}
    """
    # Ticket tier check
    if 'ticket_tiers' in criteria:
        user_tier = get_user_ticket_tier(user.id, db)
        if user_tier not in criteria['ticket_tiers']:
            return False

    # Session attendance
    if 'sessions_attended' in criteria:
        count = count_sessions_attended(user.id, db)
        if 'min' in criteria['sessions_attended'] and count < criteria['sessions_attended']['min']:
            return False
        if 'max' in criteria['sessions_attended'] and count > criteria['sessions_attended']['max']:
            return False

    # Engagement score
    if 'engagement_score' in criteria:
        score = calculate_engagement_score(user.id, db)
        if score < criteria['engagement_score'].get('min', 0):
            return False

    # Add more criteria as needed...

    return True
```

---

### 3.2 Fraud Prevention

```python
# fraud_prevention.py

from fastapi import Request
from datetime import datetime, timedelta

async def check_rate_limit(
    key: str,
    limit: int,
    window_seconds: int,
    redis: Redis
) -> bool:
    """
    Token bucket rate limiting.

    Returns True if allowed, False if limit exceeded.
    """
    current = redis.incr(f"rate_limit:{key}")
    if current == 1:
        redis.expire(f"rate_limit:{key}", window_seconds)

    return current <= limit

async def detect_suspicious_behavior(
    user_id: UUID,
    action: str,
    db: Session,
    redis: Redis
) -> bool:
    """
    Detect suspicious patterns:
    - Too many rapid purchases
    - Abnormal click patterns
    - Velocity checks
    """
    # Example: Max 5 purchases in 1 hour
    recent_purchases = redis.get(f"purchase_count:{user_id}")
    if recent_purchases and int(recent_purchases) > 5:
        return True  # Suspicious

    return False

@router.post("/offers/purchase")
async def purchase_offer_with_fraud_check(
    offer_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """Purchase with fraud prevention."""

    # Rate limit: 10 purchase attempts per minute
    if not await check_rate_limit(
        f"purchase:{current_user.id}",
        limit=10,
        window_seconds=60,
        redis=redis
    ):
        raise HTTPException(429, "Too many requests. Please try again later.")

    # Suspicious behavior check
    if await detect_suspicious_behavior(current_user.id, "purchase", db, redis):
        # Log for review, send to fraud queue
        log_fraud_alert(current_user.id, "offer_purchase", offer_id)
        raise HTTPException(403, "Transaction flagged for review")

    # Proceed with purchase...
```

---

## Infrastructure & DevOps

### Database Migrations (Alembic)

```python
# alembic/versions/001_create_monetization_tables.py

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

def upgrade():
    # Run all CREATE TABLE statements from above
    pass

def downgrade():
    # DROP TABLE statements
    pass
```

### Cron Jobs (FastAPI-utils or Celery)

```python
# cron_jobs.py

from fastapi_utils.tasks import repeat_every
from datetime import timedelta

@repeat_every(seconds=300, wait_first=True)  # Every 5 minutes
async def release_expired_offer_reservations():
    """Release expired cart reservations."""
    pass

@repeat_every(seconds=3600)  # Every hour
async def refresh_analytics_materialized_views():
    """Refresh ad_analytics_daily and conversion funnels."""
    db = get_db()
    db.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY ad_analytics_daily")
    db.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY monetization_conversion_funnels")
    db.commit()

@repeat_every(seconds=60)  # Every minute
async def process_expired_waitlist_offers():
    """Mark expired waitlist offers and offer to next person."""
    pass

@repeat_every(seconds=86400)  # Daily
async def send_daily_monetization_reports():
    """Email daily revenue reports to organizers."""
    pass
```

### Redis Configuration

```python
# config/redis.py

import redis.asyncio as redis

# Connection pool
redis_pool = redis.ConnectionPool(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True,
    max_connections=50
)

async def get_redis():
    return redis.Redis(connection_pool=redis_pool)
```

### Environment Variables

```bash
# .env

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/globalconnect

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Stripe
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# JWT
JWT_SECRET=your-super-secret-key
JWT_ALGORITHM=HS256

# Socket.io
SOCKETIO_PORT=3002
SOCKETIO_CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
```

---

## Testing Requirements

### Unit Tests

```python
# tests/test_offers.py

import pytest
from fastapi.testclient import TestClient

def test_create_offer(client: TestClient, auth_headers):
    """Test offer creation."""
    response = client.post("/api/v1/offers/", json={
        "event_id": "event-uuid",
        "title": "VIP Upgrade",
        "price": 99.99,
        "offer_type": "TICKET_UPGRADE"
    }, headers=auth_headers)

    assert response.status_code == 201
    assert response.json()["stripe_product_id"] is not None

def test_inventory_depletion(client: TestClient):
    """Test inventory decrements correctly."""
    # Create offer with inventory_total = 10
    # Purchase 10 times
    # 11th purchase should fail with 400
    pass

def test_frequency_capping(client: TestClient):
    """Test ad frequency cap."""
    # Serve ad 3 times (frequency_cap = 3)
    # 4th call should not return the same ad
    pass

# tests/test_waitlist.py

@pytest.mark.asyncio
async def test_waitlist_priority_ordering():
    """VIP users should be ahead of STANDARD users."""
    # Join as VIP user → position 1
    # Join as STANDARD user → position 2
    # Join as another VIP user → position 2 (ahead of STANDARD)
    pass

@pytest.mark.asyncio
async def test_offer_expiration():
    """Expired offers should be declined automatically."""
    # Send offer
    # Wait 6 minutes (TTL = 5 min)
    # Check status = 'EXPIRED'
    # Next user should receive offer
    pass
```

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Offer purchase API response time | < 500ms (p95) |
| Ad serving endpoint | < 100ms (p95) |
| Waitlist join | < 200ms (p95) |
| Analytics dashboard load | < 2s for 30-day data |
| Impression tracking throughput | 10,000 events/second |
| Socket.io message latency | < 50ms (p99) |
| Database query time (analytics) | < 1s |

---

## Security Checklist

- [ ] All endpoints require authentication (except public ad serving)
- [ ] SQL injection prevention (use parameterized queries)
- [ ] XSS protection (sanitize user inputs)
- [ ] CSRF tokens for state-changing operations
- [ ] Rate limiting on all public endpoints
- [ ] Stripe webhook signature verification
- [ ] JWT token expiration and rotation
- [ ] HTTPS only in production
- [ ] CORS configured for frontend domain only
- [ ] PII data encrypted at rest
- [ ] Audit logging for all monetization actions

---

## Documentation Deliverables

- [ ] OpenAPI/Swagger spec for all endpoints
- [ ] GraphQL schema documentation
- [ ] Socket.io event reference
- [ ] Database schema ERD diagram
- [ ] Postman collection for API testing
- [ ] Integration guide for frontend team
- [ ] Runbook for ops team (deployments, troubleshooting)

---

## Success Criteria

### Phase 1 Complete When:
- ✅ Offers can be purchased via Stripe
- ✅ Ads display on attendee pages with rotation
- ✅ Waitlist queue functional with real-time offers
- ✅ All endpoints covered by unit tests (>80% coverage)

### Phase 2 Complete When:
- ✅ Analytics dashboard shows accurate metrics
- ✅ Reports can be exported in CSV/Excel/PDF
- ✅ Materialized views refresh automatically
- ✅ Revenue matches Stripe reconciliation (<1% variance)

### Phase 3 Complete When:
- ✅ Targeting engine supports 10+ criteria
- ✅ Fraud detection catches >95% of suspicious activity
- ✅ Multi-channel notifications delivered reliably
- ✅ Load tests pass (10k concurrent users)

---

## Next Steps

1. **Backend Developer**: Review this document, estimate effort per section
2. **Tech Lead**: Approve architecture, allocate resources
3. **Frontend Team**: Begin integration planning based on API contracts
4. **DevOps**: Set up staging environment (PostgreSQL + Redis + FastAPI)
5. **Kickoff Meeting**: Align on priorities, timeline, dependencies

**Questions or clarifications needed? Let's discuss!**
