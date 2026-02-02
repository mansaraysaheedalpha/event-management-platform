"""
Intervention Selector
Analyzes anomalies and selects appropriate interventions
"""
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from app.agents.anomaly_detector import AnomalyEvent

logger = logging.getLogger(__name__)


@dataclass
class InterventionRecommendation:
    """Represents a recommended intervention"""
    intervention_type: str  # POLL, CHAT_PROMPT, NOTIFICATION, GAMIFICATION
    priority: str  # HIGH, MEDIUM, LOW
    confidence: float  # 0.0-1.0
    reason: str
    context: Dict[str, Any]
    estimated_impact: float  # Expected engagement increase (0.0-1.0)


class InterventionSelector:
    """
    Selects optimal interventions based on detected anomalies.

    Uses rule-based logic to match anomaly types to intervention strategies.
    Future versions will use ML to optimize selection.
    """

    # Engagement thresholds
    LOW_ENGAGEMENT_THRESHOLD = 0.4
    CRITICAL_ENGAGEMENT_THRESHOLD = 0.25

    # Intervention cooldowns (seconds)
    POLL_COOLDOWN = 120  # 2 minutes between polls
    CHAT_PROMPT_COOLDOWN = 60  # 1 minute between chat prompts
    NOTIFICATION_COOLDOWN = 300  # 5 minutes between notifications

    def __init__(self):
        """Initialize intervention selector"""
        self.last_intervention_times: Dict[str, Dict[str, datetime]] = {}
        self.intervention_history: Dict[str, List[Dict]] = {}
        self.logger = logging.getLogger(__name__)

    def select_intervention(
        self,
        anomaly: AnomalyEvent,
        session_context: Dict[str, Any]
    ) -> Optional[InterventionRecommendation]:
        """
        Select the best intervention for a detected anomaly.

        Args:
            anomaly: Detected anomaly event
            session_context: Additional session context (duration, attendees, etc.)

        Returns:
            InterventionRecommendation or None if no intervention needed
        """
        session_id = anomaly.session_id

        # Check if we should intervene based on severity
        if anomaly.severity == 'WARNING' and anomaly.current_engagement > self.LOW_ENGAGEMENT_THRESHOLD:
            self.logger.info(f"Anomaly detected but engagement still acceptable: {anomaly.current_engagement:.2f}")
            return None

        # Select intervention based on anomaly type
        if anomaly.anomaly_type == 'SUDDEN_DROP':
            return self._handle_sudden_drop(anomaly, session_context)
        elif anomaly.anomaly_type == 'GRADUAL_DECLINE':
            return self._handle_gradual_decline(anomaly, session_context)
        elif anomaly.anomaly_type == 'LOW_ENGAGEMENT':
            return self._handle_low_engagement(anomaly, session_context)
        elif anomaly.anomaly_type == 'MASS_EXIT':
            return self._handle_mass_exit(anomaly, session_context)
        else:
            self.logger.warning(f"Unknown anomaly type: {anomaly.anomaly_type}")
            return None

    def _handle_sudden_drop(
        self,
        anomaly: AnomalyEvent,
        session_context: Dict[str, Any]
    ) -> Optional[InterventionRecommendation]:
        """Handle sudden engagement drop"""
        session_id = anomaly.session_id

        # Sudden drops require immediate re-engagement
        # Best strategy: Interactive poll to capture attention

        if self._can_use_intervention(session_id, 'POLL'):
            return InterventionRecommendation(
                intervention_type='POLL',
                priority='HIGH',
                confidence=0.85,
                reason=f'Sudden engagement drop detected: {anomaly.current_engagement:.1%} (expected: {anomaly.expected_engagement:.1%})',
                context={
                    'session_id': session_id,
                    'event_id': anomaly.event_id,
                    'anomaly_type': 'SUDDEN_DROP',
                    'anomaly_score': anomaly.anomaly_score,
                    'signals': anomaly.signals,
                    'timing': 'IMMEDIATE',
                    'poll_type': 'quick_pulse'
                },
                estimated_impact=0.15  # Expect 15% engagement increase
            )
        elif self._can_use_intervention(session_id, 'CHAT_PROMPT'):
            return InterventionRecommendation(
                intervention_type='CHAT_PROMPT',
                priority='HIGH',
                confidence=0.75,
                reason='Sudden drop detected, poll on cooldown',
                context={
                    'session_id': session_id,
                    'event_id': anomaly.event_id,
                    'prompt_type': 'discussion_starter'
                },
                estimated_impact=0.10
            )
        else:
            self.logger.info(f"All interventions on cooldown for session {session_id}")
            return None

    def _handle_gradual_decline(
        self,
        anomaly: AnomalyEvent,
        session_context: Dict[str, Any]
    ) -> Optional[InterventionRecommendation]:
        """Handle gradual engagement decline"""
        session_id = anomaly.session_id

        # Gradual declines suggest fatigue or content issues
        # Strategy: Mix it up with interactive content

        if self._can_use_intervention(session_id, 'POLL'):
            return InterventionRecommendation(
                intervention_type='POLL',
                priority='MEDIUM',
                confidence=0.80,
                reason=f'Gradual engagement decline: {anomaly.current_engagement:.1%} (expected: {anomaly.expected_engagement:.1%})',
                context={
                    'session_id': session_id,
                    'event_id': anomaly.event_id,
                    'anomaly_type': 'GRADUAL_DECLINE',
                    'anomaly_score': anomaly.anomaly_score,
                    'signals': anomaly.signals,
                    'timing': 'NEXT_TRANSITION',
                    'poll_type': 'opinion'
                },
                estimated_impact=0.12
            )
        elif self._can_use_intervention(session_id, 'GAMIFICATION'):
            return InterventionRecommendation(
                intervention_type='GAMIFICATION',
                priority='MEDIUM',
                confidence=0.70,
                reason='Gradual decline, try gamification boost',
                context={
                    'session_id': session_id,
                    'event_id': anomaly.event_id,
                    'gamification_type': 'achievement_unlock'
                },
                estimated_impact=0.08
            )
        else:
            return None

    def _handle_low_engagement(
        self,
        anomaly: AnomalyEvent,
        session_context: Dict[str, Any]
    ) -> Optional[InterventionRecommendation]:
        """Handle persistently low engagement"""
        session_id = anomaly.session_id

        # Low engagement requires multi-pronged approach
        # Critical: Immediate intervention needed

        if anomaly.current_engagement <= self.CRITICAL_ENGAGEMENT_THRESHOLD:
            # Critical situation - use strongest intervention
            if self._can_use_intervention(session_id, 'NOTIFICATION'):
                return InterventionRecommendation(
                    intervention_type='NOTIFICATION',
                    priority='HIGH',
                    confidence=0.75,
                    reason=f'Critical low engagement: {anomaly.current_engagement:.1%}',
                    context={
                        'session_id': session_id,
                        'event_id': anomaly.event_id,
                        'notification_type': 'disengagement_nudge',
                        'target': 'inactive_users'
                    },
                    estimated_impact=0.18
                )

        # Standard low engagement
        if self._can_use_intervention(session_id, 'POLL'):
            return InterventionRecommendation(
                intervention_type='POLL',
                priority='HIGH',
                confidence=0.82,
                reason=f'Low engagement detected: {anomaly.current_engagement:.1%}',
                context={
                    'session_id': session_id,
                    'event_id': anomaly.event_id,
                    'anomaly_type': 'LOW_ENGAGEMENT',
                    'signals': anomaly.signals,
                    'timing': 'IMMEDIATE',
                    'poll_type': 'engaging'
                },
                estimated_impact=0.14
            )
        else:
            return None

    def _handle_mass_exit(
        self,
        anomaly: AnomalyEvent,
        session_context: Dict[str, Any]
    ) -> Optional[InterventionRecommendation]:
        """Handle mass exit event"""
        session_id = anomaly.session_id

        # Mass exits are critical - may indicate technical issues or major content problem
        # Need immediate attention and potentially human escalation

        return InterventionRecommendation(
            intervention_type='NOTIFICATION',
            priority='HIGH',
            confidence=0.90,
            reason=f'Mass exit detected: {anomaly.signals.get("user_leave_rate", 0):.1%} leave rate',
            context={
                'session_id': session_id,
                'event_id': anomaly.event_id,
                'notification_type': 'crisis_alert',
                'target': 'organizer',
                'escalate': True,
                'retention_message': True
            },
            estimated_impact=0.10  # Lower impact, may need human intervention
        )

    def _can_use_intervention(
        self,
        session_id: str,
        intervention_type: str
    ) -> bool:
        """
        Check if an intervention type is available (not on cooldown).

        Args:
            session_id: Session identifier
            intervention_type: Type of intervention

        Returns:
            True if intervention can be used
        """
        if session_id not in self.last_intervention_times:
            self.last_intervention_times[session_id] = {}

        last_time = self.last_intervention_times[session_id].get(intervention_type)

        if last_time is None:
            return True

        # Get cooldown for intervention type
        cooldowns = {
            'POLL': self.POLL_COOLDOWN,
            'CHAT_PROMPT': self.CHAT_PROMPT_COOLDOWN,
            'NOTIFICATION': self.NOTIFICATION_COOLDOWN,
            'GAMIFICATION': 180,  # 3 minutes
        }

        cooldown = cooldowns.get(intervention_type, 60)
        time_since_last = (datetime.now(timezone.utc) - last_time).total_seconds()

        return time_since_last >= cooldown

    def record_intervention(
        self,
        session_id: str,
        intervention_type: str,
        recommendation: InterventionRecommendation
    ):
        """
        Record that an intervention was used.

        Args:
            session_id: Session identifier
            intervention_type: Type of intervention used
            recommendation: The intervention recommendation that was executed
        """
        if session_id not in self.last_intervention_times:
            self.last_intervention_times[session_id] = {}

        self.last_intervention_times[session_id][intervention_type] = datetime.now(timezone.utc)

        # Track history
        if session_id not in self.intervention_history:
            self.intervention_history[session_id] = []

        self.intervention_history[session_id].append({
            'timestamp': datetime.now(timezone.utc),
            'type': intervention_type,
            'recommendation': recommendation,
        })

        self.logger.info(
            f"✅ Intervention recorded: {session_id[:8]}... - {intervention_type} "
            f"(confidence: {recommendation.confidence:.2f})"
        )

    def get_session_interventions(
        self,
        session_id: str
    ) -> List[Dict]:
        """
        Get intervention history for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of intervention records
        """
        return self.intervention_history.get(session_id, [])

    def cleanup_session(self, session_id: str):
        """
        Clean up intervention state for a session.

        Args:
            session_id: Session identifier
        """
        if session_id in self.last_intervention_times:
            del self.last_intervention_times[session_id]
        if session_id in self.intervention_history:
            del self.intervention_history[session_id]
        self.logger.info(f"🧹 Cleaned up intervention selector for session {session_id}")


# Global instance
intervention_selector = InterventionSelector()
