"""
Engagement Score Calculation
Combines multiple signals into a single engagement score (0.0 to 1.0)
"""
from dataclasses import dataclass
from typing import Optional
import math


@dataclass
class EngagementSignals:
    """Raw engagement signals collected from the platform"""
    chat_msgs_per_min: float = 0.0
    poll_participation: float = 0.0  # 0.0 to 1.0
    active_users: int = 0
    reactions_per_min: float = 0.0
    user_leave_rate: float = 0.0  # 0.0 to 1.0 (higher is worse)
    total_users: int = 0


class EngagementScoreCalculator:
    """
    Calculates engagement score using weighted combination of signals.

    Score formula:
    - Chat activity: 30% weight
    - Poll participation: 25% weight
    - Active users ratio: 25% weight
    - Reactions: 10% weight
    - Leave rate (penalty): -10% weight

    Final score is normalized to 0.0 - 1.0 range.
    """

    # Weights for each signal
    CHAT_WEIGHT = 0.30
    POLL_WEIGHT = 0.25
    ACTIVE_USERS_WEIGHT = 0.25
    REACTIONS_WEIGHT = 0.10
    LEAVE_RATE_PENALTY = 0.10

    # Normalization parameters (based on typical event patterns)
    MAX_CHAT_MSGS_PER_MIN = 20.0  # High engagement events
    MAX_REACTIONS_PER_MIN = 10.0

    def __init__(self):
        """Initialize the calculator"""
        pass

    def calculate(self, signals: EngagementSignals) -> float:
        """
        Calculate engagement score from signals.

        Args:
            signals: Raw engagement signals

        Returns:
            Engagement score between 0.0 and 1.0
        """
        score = 0.0

        # 1. Chat activity score (normalized)
        chat_score = self._normalize_chat_activity(signals.chat_msgs_per_min)
        score += chat_score * self.CHAT_WEIGHT

        # 2. Poll participation score (already 0-1)
        score += signals.poll_participation * self.POLL_WEIGHT

        # 3. Active users ratio
        active_ratio = self._calculate_active_ratio(
            signals.active_users,
            signals.total_users
        )
        score += active_ratio * self.ACTIVE_USERS_WEIGHT

        # 4. Reactions score (normalized)
        reactions_score = self._normalize_reactions(signals.reactions_per_min)
        score += reactions_score * self.REACTIONS_WEIGHT

        # 5. Leave rate penalty
        score -= signals.user_leave_rate * self.LEAVE_RATE_PENALTY

        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))

    def _normalize_chat_activity(self, msgs_per_min: float) -> float:
        """
        Normalize chat messages per minute to 0-1 scale.
        Uses sigmoid-like curve for smooth scaling.

        Args:
            msgs_per_min: Messages per minute

        Returns:
            Normalized score (0.0 to 1.0)
        """
        if msgs_per_min <= 0:
            return 0.0

        # Logarithmic scaling (more forgiving for low values)
        normalized = math.log(msgs_per_min + 1) / math.log(self.MAX_CHAT_MSGS_PER_MIN + 1)
        return min(1.0, normalized)

    def _normalize_reactions(self, reactions_per_min: float) -> float:
        """
        Normalize reactions per minute to 0-1 scale.

        Args:
            reactions_per_min: Reactions per minute

        Returns:
            Normalized score (0.0 to 1.0)
        """
        if reactions_per_min <= 0:
            return 0.0

        normalized = math.log(reactions_per_min + 1) / math.log(self.MAX_REACTIONS_PER_MIN + 1)
        return min(1.0, normalized)

    def _calculate_active_ratio(self, active_users: int, total_users: int) -> float:
        """
        Calculate ratio of active users to total users.

        Args:
            active_users: Number of active users
            total_users: Total number of users in session

        Returns:
            Active ratio (0.0 to 1.0)
        """
        if total_users <= 0:
            return 0.0

        ratio = active_users / total_users
        return min(1.0, ratio)

    def categorize_engagement(self, score: float) -> str:
        """
        Categorize engagement level based on score.

        Args:
            score: Engagement score (0.0 to 1.0)

        Returns:
            Category string
        """
        if score >= 0.8:
            return "VERY_HIGH"
        elif score >= 0.6:
            return "HIGH"
        elif score >= 0.4:
            return "MODERATE"
        elif score >= 0.2:
            return "LOW"
        else:
            return "VERY_LOW"

    def explain_score(self, signals: EngagementSignals, score: float) -> dict:
        """
        Provide detailed breakdown of engagement score.
        Useful for debugging and agent reasoning.

        Args:
            signals: Raw signals used
            score: Calculated score

        Returns:
            Dictionary with score breakdown
        """
        chat_score = self._normalize_chat_activity(signals.chat_msgs_per_min)
        reactions_score = self._normalize_reactions(signals.reactions_per_min)
        active_ratio = self._calculate_active_ratio(signals.active_users, signals.total_users)

        return {
            "overall_score": score,
            "category": self.categorize_engagement(score),
            "breakdown": {
                "chat_activity": {
                    "normalized_score": chat_score,
                    "weight": self.CHAT_WEIGHT,
                    "contribution": chat_score * self.CHAT_WEIGHT,
                    "raw_value": signals.chat_msgs_per_min,
                },
                "poll_participation": {
                    "score": signals.poll_participation,
                    "weight": self.POLL_WEIGHT,
                    "contribution": signals.poll_participation * self.POLL_WEIGHT,
                },
                "active_users": {
                    "ratio": active_ratio,
                    "weight": self.ACTIVE_USERS_WEIGHT,
                    "contribution": active_ratio * self.ACTIVE_USERS_WEIGHT,
                    "raw_value": f"{signals.active_users}/{signals.total_users}",
                },
                "reactions": {
                    "normalized_score": reactions_score,
                    "weight": self.REACTIONS_WEIGHT,
                    "contribution": reactions_score * self.REACTIONS_WEIGHT,
                    "raw_value": signals.reactions_per_min,
                },
                "leave_rate_penalty": {
                    "rate": signals.user_leave_rate,
                    "penalty": self.LEAVE_RATE_PENALTY,
                    "contribution": -signals.user_leave_rate * self.LEAVE_RATE_PENALTY,
                },
            },
        }


# Global instance
engagement_calculator = EngagementScoreCalculator()
