"""
Anomaly Detector
Detects engagement drops and classifies anomaly types using online learning

RELIABILITY: Memory bounded with LRU eviction and TTL to prevent unbounded growth.
"""
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from collections import deque, OrderedDict
import statistics

from river import anomaly, preprocessing

logger = logging.getLogger(__name__)


class BoundedTTLCache:
    """
    A bounded cache with LRU eviction and TTL (time-to-live).

    Memory-safe for high-concurrency scenarios with thousands of sessions.
    """

    def __init__(self, maxsize: int = 10000, ttl_seconds: int = 3600):
        """
        Initialize bounded cache.

        Args:
            maxsize: Maximum number of entries (default: 10,000 sessions)
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
        """
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expired': 0,
        }

    def get(self, key: str) -> Optional[any]:
        """Get item from cache, returning None if expired or missing."""
        with self._lock:
            if key not in self._cache:
                self._stats['misses'] += 1
                return None

            # Check TTL
            if time.time() - self._timestamps[key] > self.ttl_seconds:
                # Expired
                self._remove_key(key)
                self._stats['expired'] += 1
                self._stats['misses'] += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._stats['hits'] += 1
            return self._cache[key]

    def set(self, key: str, value: any) -> None:
        """Set item in cache with LRU eviction if needed."""
        with self._lock:
            now = time.time()

            if key in self._cache:
                # Update existing
                self._cache[key] = value
                self._timestamps[key] = now
                self._cache.move_to_end(key)
                return

            # Evict if at capacity
            while len(self._cache) >= self.maxsize:
                # Remove oldest (first item in OrderedDict)
                oldest_key = next(iter(self._cache))
                self._remove_key(oldest_key)
                self._stats['evictions'] += 1
                logger.debug(f"LRU eviction: removed {oldest_key}")

            # Add new item
            self._cache[key] = value
            self._timestamps[key] = now

    def _remove_key(self, key: str) -> None:
        """Remove a key from cache (must hold lock)."""
        if key in self._cache:
            del self._cache[key]
        if key in self._timestamps:
            del self._timestamps[key]

    def delete(self, key: str) -> None:
        """Delete item from cache."""
        with self._lock:
            self._remove_key(key)

    def contains(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return self.get(key) is not None

    def cleanup_expired(self) -> int:
        """Clean up expired entries. Returns count of removed items."""
        with self._lock:
            now = time.time()
            expired_keys = [
                k for k, ts in self._timestamps.items()
                if now - ts > self.ttl_seconds
            ]
            for key in expired_keys:
                self._remove_key(key)
                self._stats['expired'] += 1
            return len(expired_keys)

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        return self.contains(key)

    @property
    def stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            return {
                **self._stats,
                'size': len(self._cache),
                'maxsize': self.maxsize,
                'hit_rate': self._stats['hits'] / max(1, self._stats['hits'] + self._stats['misses']),
            }


@dataclass
class AnomalyEvent:
    """Represents a detected anomaly"""
    session_id: str
    event_id: str
    timestamp: datetime
    anomaly_type: str  # SUDDEN_DROP, GRADUAL_DECLINE, LOW_ENGAGEMENT, MASS_EXIT
    severity: str  # WARNING, CRITICAL
    anomaly_score: float
    current_engagement: float
    expected_engagement: float
    deviation: float
    signals: dict
    metadata: dict = None


class AnomalyDetector:
    """
    Detects anomalies in engagement scores using:
    1. River's HalfSpaceTrees for online anomaly detection
    2. Z-score method as baseline
    3. Rule-based classification

    RELIABILITY: Memory bounded with LRU eviction and TTL to handle
    thousands of concurrent sessions without memory exhaustion.

    Configuration:
        - MAX_SESSIONS: Maximum number of sessions to track (default: 10,000)
        - SESSION_TTL: Time-to-live for session data in seconds (default: 2 hours)
    """

    # Memory bounds configuration
    MAX_SESSIONS = 10000  # Maximum concurrent sessions
    SESSION_TTL_SECONDS = 7200  # 2 hours TTL

    # Anomaly thresholds
    WARNING_THRESHOLD = 0.6  # Anomaly score threshold for warning
    CRITICAL_THRESHOLD = 0.8  # Anomaly score threshold for critical

    # Engagement thresholds
    LOW_ENGAGEMENT_THRESHOLD = 0.3
    CRITICAL_ENGAGEMENT_THRESHOLD = 0.2

    # Change detection thresholds
    SUDDEN_DROP_PERCENT = 0.25  # 25% drop
    GRADUAL_DECLINE_WINDOW = 6  # 6 data points (30 seconds)
    MASS_EXIT_RATE = 0.15  # 15% of users leaving

    def __init__(
        self,
        window_size: int = 30,
        n_trees: int = 10,
        height: int = 8,
        seed: int = 42,
        max_sessions: int = None,
        session_ttl_seconds: int = None
    ):
        """
        Initialize the anomaly detector with memory bounds.

        Args:
            window_size: Number of historical points to keep for baseline
            n_trees: Number of trees for HalfSpaceTrees
            height: Tree height for HalfSpaceTrees
            seed: Random seed for reproducibility
            max_sessions: Maximum sessions to track (default: MAX_SESSIONS)
            session_ttl_seconds: Session TTL in seconds (default: SESSION_TTL_SECONDS)
        """
        self.window_size = window_size

        # Memory bounds
        max_sessions = max_sessions or self.MAX_SESSIONS
        session_ttl = session_ttl_seconds or self.SESSION_TTL_SECONDS

        # Per-session state with bounded caches
        self.session_detectors = BoundedTTLCache(
            maxsize=max_sessions,
            ttl_seconds=session_ttl
        )
        self.session_scalers = BoundedTTLCache(
            maxsize=max_sessions,
            ttl_seconds=session_ttl
        )
        self.engagement_history = BoundedTTLCache(
            maxsize=max_sessions,
            ttl_seconds=session_ttl
        )

        # Configuration for new detectors
        self.n_trees = n_trees
        self.height = height
        self.seed = seed

        self.logger = logging.getLogger(__name__)
        self.logger.info(
            f"AnomalyDetector initialized with memory bounds: "
            f"max_sessions={max_sessions}, ttl={session_ttl}s"
        )

    def get_or_create_detector(self, session_id: str) -> Tuple[anomaly.HalfSpaceTrees, preprocessing.StandardScaler]:
        """
        Get or create detector and scaler for a session.

        RELIABILITY: Uses bounded cache with LRU eviction.

        Args:
            session_id: Session identifier

        Returns:
            Tuple of (detector, scaler)
        """
        detector = self.session_detectors.get(session_id)
        scaler = self.session_scalers.get(session_id)

        if detector is None or scaler is None:
            self.logger.info(f"Creating anomaly detector for session {session_id[:8]}...")

            # Create HalfSpaceTrees detector
            detector = anomaly.HalfSpaceTrees(
                n_trees=self.n_trees,
                height=self.height,
                seed=self.seed
            )
            self.session_detectors.set(session_id, detector)

            # Create StandardScaler for normalization
            scaler = preprocessing.StandardScaler()
            self.session_scalers.set(session_id, scaler)

            # Create engagement history
            self.engagement_history.set(session_id, deque(maxlen=self.window_size))

        return detector, scaler

    def detect(
        self,
        session_id: str,
        event_id: str,
        engagement_score: float,
        signals: dict
    ) -> Optional[AnomalyEvent]:
        """
        Detect anomalies in engagement score.

        Args:
            session_id: Session identifier
            event_id: Event identifier
            engagement_score: Current engagement score (0-1)
            signals: Engagement signals dictionary

        Returns:
            AnomalyEvent if anomaly detected, None otherwise
        """
        # Get or create detector
        detector, scaler = self.get_or_create_detector(session_id)
        history = self.engagement_history.get(session_id)

        # Safety check - history should exist after get_or_create_detector
        if history is None:
            history = deque(maxlen=self.window_size)
            self.engagement_history.set(session_id, history)

        # Need at least 5 data points to establish baseline
        if len(history) < 5:
            history.append({
                'score': engagement_score,
                'timestamp': datetime.now(timezone.utc),
                'signals': signals
            })
            return None

        # Create feature vector
        features = {
            'engagement_score': engagement_score,
            'chat_rate': signals.get('chat_msgs_per_min', 0),
            'active_users': signals.get('active_users', 0),
            'poll_participation': signals.get('poll_participation', 0),
        }

        # Scale features - River's learn_one may return None in some versions
        scaler.learn_one(features)
        scaled_features = scaler.transform_one(features)

        # Get anomaly score from detector
        anomaly_score = detector.score_one(scaled_features)
        detector.learn_one(scaled_features)

        # Calculate z-score for engagement
        recent_scores = [h['score'] for h in history]
        mean_score = statistics.mean(recent_scores)
        std_score = statistics.stdev(recent_scores) if len(recent_scores) > 1 else 0.1
        z_score = abs((engagement_score - mean_score) / std_score) if std_score > 0 else 0

        # Combine scores (weighted average)
        combined_score = (anomaly_score * 0.7) + (min(z_score / 3, 1.0) * 0.3)

        # Add current point to history
        history.append({
            'score': engagement_score,
            'timestamp': datetime.now(timezone.utc),
            'signals': signals
        })

        # Check if anomaly detected
        if combined_score < self.WARNING_THRESHOLD:
            return None

        # Determine severity
        severity = 'CRITICAL' if combined_score >= self.CRITICAL_THRESHOLD else 'WARNING'

        # Classify anomaly type
        anomaly_type = self._classify_anomaly_type(
            engagement_score,
            recent_scores,
            signals,
            history
        )

        # Create anomaly event
        anomaly_event = AnomalyEvent(
            session_id=session_id,
            event_id=event_id,
            timestamp=datetime.now(timezone.utc),
            anomaly_type=anomaly_type,
            severity=severity,
            anomaly_score=combined_score,
            current_engagement=engagement_score,
            expected_engagement=mean_score,
            deviation=abs(engagement_score - mean_score),
            signals=signals,
            metadata={
                'z_score': z_score,
                'river_score': anomaly_score,
                'history_length': len(history)
            }
        )

        self.logger.warning(
            f"🚨 Anomaly detected: {session_id[:8]}... - {anomaly_type} ({severity}) - "
            f"Score: {engagement_score:.2f} (expected: {mean_score:.2f})"
        )

        return anomaly_event

    def _classify_anomaly_type(
        self,
        current_score: float,
        recent_scores: List[float],
        signals: dict,
        history: deque
    ) -> str:
        """
        Classify the type of anomaly.

        Args:
            current_score: Current engagement score
            recent_scores: List of recent scores
            signals: Current signals
            history: Full history deque

        Returns:
            Anomaly type string
        """
        # Check for mass exit (high leave rate)
        leave_rate = signals.get('user_leave_rate', 0)
        if leave_rate >= self.MASS_EXIT_RATE:
            return 'MASS_EXIT'

        # Check for low engagement
        if current_score <= self.CRITICAL_ENGAGEMENT_THRESHOLD:
            return 'LOW_ENGAGEMENT'

        # Check for sudden drop (compared to last point)
        if len(recent_scores) >= 2:
            previous_score = recent_scores[-2]
            drop_percent = (previous_score - current_score) / previous_score if previous_score > 0 else 0

            if drop_percent >= self.SUDDEN_DROP_PERCENT:
                return 'SUDDEN_DROP'

        # Check for gradual decline (trend over window)
        if len(recent_scores) >= self.GRADUAL_DECLINE_WINDOW:
            window_scores = recent_scores[-self.GRADUAL_DECLINE_WINDOW:]

            # Calculate trend (simple linear regression slope)
            n = len(window_scores)
            x_mean = (n - 1) / 2
            y_mean = statistics.mean(window_scores)

            numerator = sum((i - x_mean) * (score - y_mean) for i, score in enumerate(window_scores))
            denominator = sum((i - x_mean) ** 2 for i in range(n))

            slope = numerator / denominator if denominator != 0 else 0

            # Negative slope indicates decline
            if slope < -0.02:  # Declining trend
                return 'GRADUAL_DECLINE'

        # Default to sudden drop if we can't classify more specifically
        return 'SUDDEN_DROP'

    def get_session_baseline(self, session_id: str) -> Optional[float]:
        """
        Get the baseline engagement score for a session.

        Args:
            session_id: Session identifier

        Returns:
            Baseline score or None if not enough data
        """
        history = self.engagement_history.get(session_id)
        if not history or len(history) < 5:
            return None

        scores = [h['score'] for h in history]
        return statistics.mean(scores)

    def cleanup_session(self, session_id: str):
        """
        Clean up detector state for a session.

        Args:
            session_id: Session identifier
        """
        self.session_detectors.delete(session_id)
        self.session_scalers.delete(session_id)
        self.engagement_history.delete(session_id)
        self.logger.info(f"Cleaned up anomaly detector for session {session_id[:8]}...")

    def cleanup_expired(self) -> int:
        """
        Clean up expired sessions from all caches.

        Returns:
            Number of sessions cleaned up
        """
        count = 0
        count += self.session_detectors.cleanup_expired()
        count += self.session_scalers.cleanup_expired()
        count += self.engagement_history.cleanup_expired()
        if count > 0:
            self.logger.info(f"Cleaned up {count} expired anomaly detector entries")
        return count

    def get_cache_stats(self) -> Dict:
        """Get statistics for all caches."""
        return {
            'detectors': self.session_detectors.stats,
            'scalers': self.session_scalers.stats,
            'history': self.engagement_history.stats,
        }


# Global instance
anomaly_detector = AnomalyDetector()
