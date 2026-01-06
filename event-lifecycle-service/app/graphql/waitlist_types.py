# app/graphql/waitlist_types.py
"""
GraphQL types for Waitlist Management System.

Provides type definitions for:
- Waitlist entries
- Waitlist positions
- Session capacity
- Waitlist analytics
"""

import strawberry
from typing import Optional, List
from datetime import datetime
from enum import Enum


@strawberry.enum
class WaitlistStatus(str, Enum):
    """Waitlist entry status"""
    WAITING = "WAITING"
    OFFERED = "OFFERED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    LEFT = "LEFT"


@strawberry.enum
class PriorityTier(str, Enum):
    """Priority tier for waitlist queue"""
    VIP = "VIP"
    PREMIUM = "PREMIUM"
    STANDARD = "STANDARD"


@strawberry.type
class WaitlistUserType:
    """User information for waitlist display"""
    id: str
    email: str
    first_name: str
    last_name: str
    image_url: Optional[str]


@strawberry.type
class WaitlistEntryType:
    """A waitlist entry for a session"""
    id: str
    session_id: str
    user_id: str
    user: Optional[WaitlistUserType]  # Populated from user service
    status: WaitlistStatus
    priority_tier: PriorityTier
    position: int
    joined_at: datetime
    offer_sent_at: Optional[datetime]
    offer_expires_at: Optional[datetime]
    offer_responded_at: Optional[datetime]
    left_at: Optional[datetime]


@strawberry.type
class WaitlistPositionType:
    """Current position information for a user in waitlist"""
    position: int
    total: int
    estimated_wait_minutes: Optional[int]
    priority_tier: PriorityTier
    status: WaitlistStatus


@strawberry.type
class SessionCapacityType:
    """Session capacity information"""
    session_id: str
    maximum_capacity: int
    current_attendance: int
    available_spots: int
    is_available: bool
    waitlist_count: int


@strawberry.type
class WaitlistJoinResponseType:
    """Response when joining a waitlist"""
    id: str
    session_id: str
    position: int
    priority_tier: PriorityTier
    estimated_wait_minutes: Optional[int]
    joined_at: datetime


@strawberry.type
class WaitlistAcceptOfferResponseType:
    """Response when accepting a waitlist offer"""
    success: bool
    message: str
    session_id: str


@strawberry.type
class WaitlistLeaveResponseType:
    """Response when leaving a waitlist"""
    success: bool
    message: str


@strawberry.type
class WaitlistStatsByPriorityType:
    """Waitlist statistics by priority tier"""
    vip: int
    premium: int
    standard: int
    redis_vip: int
    redis_premium: int
    redis_standard: int


@strawberry.type
class WaitlistStatsType:
    """Comprehensive waitlist statistics for a session"""
    session_id: str
    total_waiting: int
    total_offered: int
    total_accepted: int
    total_declined: int
    total_expired: int
    total_left: int
    by_priority: WaitlistStatsByPriorityType


@strawberry.type
class EventWaitlistAnalyticsType:
    """Comprehensive event-level waitlist analytics"""
    event_id: str
    total_waitlist_entries: float
    active_waitlist_count: float
    total_offers_issued: float
    total_offers_accepted: float
    total_offers_declined: float
    total_offers_expired: float
    acceptance_rate: float
    decline_rate: float
    expiry_rate: float
    conversion_rate: float
    average_wait_time_minutes: float
    cached_at: Optional[str]


@strawberry.type
class BulkSendOffersResponseType:
    """Response for bulk sending waitlist offers"""
    success: bool
    offers_sent: int
    message: str


@strawberry.type
class UpdateCapacityResponseType:
    """Response for updating session capacity"""
    session_id: str
    maximum_capacity: int
    current_attendance: int
    available_spots: int
    is_available: bool
    offers_automatically_sent: int


# ==================== Input Types ====================

@strawberry.input
class JoinWaitlistInput:
    """Input for joining a waitlist"""
    session_id: str


@strawberry.input
class LeaveWaitlistInput:
    """Input for leaving a waitlist"""
    session_id: str


@strawberry.input
class AcceptOfferInput:
    """Input for accepting a waitlist offer"""
    session_id: str
    join_token: str


@strawberry.input
class DeclineOfferInput:
    """Input for declining a waitlist offer"""
    session_id: str


@strawberry.input
class RemoveFromWaitlistInput:
    """Input for admin removing user from waitlist"""
    session_id: str
    user_id: str
    reason: Optional[str] = "Removed by admin"


@strawberry.input
class SendOfferInput:
    """Input for manually sending offer to user"""
    session_id: str
    user_id: str
    expires_minutes: Optional[int] = 5


@strawberry.input
class BulkSendOffersInput:
    """Input for bulk sending offers"""
    session_id: str
    count: int
    expires_minutes: Optional[int] = 5


@strawberry.input
class UpdateCapacityInput:
    """Input for updating session capacity"""
    session_id: str
    capacity: int
