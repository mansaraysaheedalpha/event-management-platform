"""
Session Tracker
Maintains per-session state and tracks engagement signals over time
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Helper function for timezone-aware UTC datetime (for dataclass defaults)."""
    return datetime.now(timezone.utc)


@dataclass
class SessionState:
    """State for a single session"""
    session_id: str
    event_id: str
    created_at: datetime = field(default_factory=_utc_now)
    last_updated: datetime = field(default_factory=_utc_now)

    # Current signal values
    chat_msgs_per_min: float = 0.0
    poll_participation: float = 0.0
    active_users: int = 0
    total_users: int = 0
    reactions_per_min: float = 0.0
    user_leave_rate: float = 0.0

    # Tracking for rate calculations
    chat_messages: deque = field(default_factory=lambda: deque(maxlen=60))  # Last 60 seconds
    reactions: deque = field(default_factory=lambda: deque(maxlen=60))
    user_joins: deque = field(default_factory=lambda: deque(maxlen=60))
    user_leaves: deque = field(default_factory=lambda: deque(maxlen=60))

    # Active poll tracking
    active_poll_id: Optional[str] = None
    poll_total_votes: int = 0
    poll_eligible_users: int = 0

    # Connected users (for presence tracking)
    connected_users: set = field(default_factory=set)

    def update_timestamp(self):
        """Update last_updated timestamp"""
        self.last_updated = datetime.now(timezone.utc)


class SessionTracker:
    """
    Tracks state for multiple sessions.
    Maintains rolling windows for rate calculations.
    """

    def __init__(self, session_timeout_minutes: int = 30):
        """
        Initialize session tracker.

        Args:
            session_timeout_minutes: Minutes before inactive session is cleaned up
        """
        self.sessions: Dict[str, SessionState] = {}
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.logger = logging.getLogger(__name__)

    def get_or_create_session(self, session_id: str, event_id: str) -> SessionState:
        """
        Get existing session or create new one.

        Args:
            session_id: Session identifier
            event_id: Parent event identifier

        Returns:
            SessionState object
        """
        if session_id not in self.sessions:
            self.logger.info(f"📊 Creating new session tracker: {session_id}")
            self.sessions[session_id] = SessionState(
                session_id=session_id,
                event_id=event_id
            )

        return self.sessions[session_id]

    def record_chat_message(self, session_id: str, event_id: str):
        """
        Record a chat message.

        Args:
            session_id: Session identifier
            event_id: Event identifier
        """
        session = self.get_or_create_session(session_id, event_id)
        session.chat_messages.append(datetime.now(timezone.utc))
        session.update_timestamp()

        # Recalculate chat rate
        self._update_chat_rate(session)

    def record_reaction(self, session_id: str, event_id: str):
        """
        Record a reaction (emoji, like, etc.).

        Args:
            session_id: Session identifier
            event_id: Event identifier
        """
        session = self.get_or_create_session(session_id, event_id)
        session.reactions.append(datetime.now(timezone.utc))
        session.update_timestamp()

        # Recalculate reaction rate
        self._update_reaction_rate(session)

    def record_user_join(self, session_id: str, event_id: str, user_id: str):
        """
        Record a user joining the session.

        Args:
            session_id: Session identifier
            event_id: Event identifier
            user_id: User identifier
        """
        session = self.get_or_create_session(session_id, event_id)
        session.connected_users.add(user_id)
        session.user_joins.append(datetime.now(timezone.utc))
        session.update_timestamp()

        # Update user counts
        self._update_user_counts(session)

    def record_user_leave(self, session_id: str, event_id: str, user_id: str):
        """
        Record a user leaving the session.

        Args:
            session_id: Session identifier
            event_id: Event identifier
            user_id: User identifier
        """
        session = self.get_or_create_session(session_id, event_id)
        session.connected_users.discard(user_id)
        session.user_leaves.append(datetime.now(timezone.utc))
        session.update_timestamp()

        # Update user counts and leave rate
        self._update_user_counts(session)
        self._update_leave_rate(session)

    def record_poll_vote(self, session_id: str, event_id: str, poll_id: str):
        """
        Record a poll vote.

        Args:
            session_id: Session identifier
            event_id: Event identifier
            poll_id: Poll identifier
        """
        session = self.get_or_create_session(session_id, event_id)

        if session.active_poll_id != poll_id:
            # New poll, reset counters
            session.active_poll_id = poll_id
            session.poll_total_votes = 0
            session.poll_eligible_users = max(len(session.connected_users), 1)

        session.poll_total_votes += 1
        session.update_timestamp()

        # Update poll participation rate
        self._update_poll_participation(session)

    def _update_chat_rate(self, session: SessionState):
        """Calculate messages per minute from rolling window"""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=60)

        # Count messages in last 60 seconds
        recent_messages = sum(1 for ts in session.chat_messages if ts >= cutoff)
        session.chat_msgs_per_min = float(recent_messages)

    def _update_reaction_rate(self, session: SessionState):
        """Calculate reactions per minute from rolling window"""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=60)

        recent_reactions = sum(1 for ts in session.reactions if ts >= cutoff)
        session.reactions_per_min = float(recent_reactions)

    def _update_user_counts(self, session: SessionState):
        """Update active and total user counts"""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=60)

        # Active users: those who have activity in last 60 seconds
        # For now, use connected users as a proxy
        session.active_users = len(session.connected_users)
        session.total_users = max(len(session.connected_users), 1)

    def _update_leave_rate(self, session: SessionState):
        """Calculate user leave rate (leaves per minute / total users)"""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=60)

        recent_leaves = sum(1 for ts in session.user_leaves if ts >= cutoff)

        if session.total_users > 0:
            session.user_leave_rate = recent_leaves / session.total_users
        else:
            session.user_leave_rate = 0.0

    def _update_poll_participation(self, session: SessionState):
        """Calculate poll participation rate"""
        if session.poll_eligible_users > 0:
            session.poll_participation = min(
                1.0,
                session.poll_total_votes / session.poll_eligible_users
            )
        else:
            session.poll_participation = 0.0

    def get_session_signals(self, session_id: str) -> Optional[Dict]:
        """
        Get current engagement signals for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary of signals, or None if session doesn't exist
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        return {
            "chat_msgs_per_min": session.chat_msgs_per_min,
            "poll_participation": session.poll_participation,
            "active_users": session.active_users,
            "total_users": session.total_users,
            "reactions_per_min": session.reactions_per_min,
            "user_leave_rate": session.user_leave_rate,
        }

    def cleanup_inactive_sessions(self):
        """Remove sessions that haven't been updated recently"""
        now = datetime.now(timezone.utc)
        inactive_sessions = [
            session_id
            for session_id, session in self.sessions.items()
            if now - session.last_updated > self.session_timeout
        ]

        for session_id in inactive_sessions:
            self.logger.info(f"🧹 Cleaning up inactive session: {session_id}")
            del self.sessions[session_id]

        return len(inactive_sessions)

    def get_active_session_count(self) -> int:
        """Get number of active sessions being tracked"""
        return len(self.sessions)


# Global instance
session_tracker = SessionTracker()
