"""
Poll Intervention Strategy
Generates poll questions for engagement interventions
"""
import logging
import random
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PollQuestion:
    """Represents a generated poll question"""
    question: str
    options: List[str]
    poll_type: str  # MULTIPLE_CHOICE, RATING, YES_NO, OPEN_ENDED
    duration: int  # seconds
    reason: str
    context: Dict[str, Any]


class PollInterventionStrategy:
    """
    Generates poll questions for engagement interventions.

    Phase 3 (Manual Mode): Uses rule-based poll templates
    Phase 4 (LLM Integration): Uses AI to generate contextual polls with template fallback
    """

    # Poll templates by type
    QUICK_PULSE_POLLS = [
        {
            'question': 'How are you finding this session so far?',
            'options': ['Excellent', 'Good', 'OK', 'Could be better'],
            'duration': 60
        },
        {
            'question': 'Is the pace of this session working for you?',
            'options': ['Too fast', 'Just right', 'Too slow'],
            'duration': 60
        },
        {
            'question': 'What would make this session more valuable?',
            'options': ['More examples', 'Deeper technical detail', 'More Q&A', 'Different format'],
            'duration': 90
        },
        {
            'question': 'Are you getting what you expected from this session?',
            'options': ['Yes, exactly', 'Mostly yes', 'Not quite', 'No, different than expected'],
            'duration': 60
        }
    ]

    OPINION_POLLS = [
        {
            'question': 'Which topic interests you most?',
            'options': ['Current topic', 'Related applications', 'Advanced techniques', 'Best practices'],
            'duration': 90
        },
        {
            'question': 'What challenge are you trying to solve?',
            'options': ['Learning the basics', 'Implementing in production', 'Scaling solution', 'Troubleshooting'],
            'duration': 90
        },
        {
            'question': 'What would you like to explore next?',
            'options': ['Deep dive current topic', 'New related topic', 'Hands-on demo', 'Case studies'],
            'duration': 90
        }
    ]

    ENGAGING_POLLS = [
        {
            'question': 'Quick prediction: What do you think will happen?',
            'options': ['Option A wins', 'Option B wins', 'Tie', 'Something unexpected'],
            'duration': 60
        },
        {
            'question': 'Have you tried this before?',
            'options': ['Yes, successfully', 'Yes, had issues', 'No, but planning to', 'No, just learning'],
            'duration': 75
        },
        {
            'question': 'What\'s your biggest takeaway so far?',
            'options': ['New concept learned', 'Practical application', 'Problem solved', 'Questions answered'],
            'duration': 75
        },
        {
            'question': 'Would you recommend this to a colleague?',
            'options': ['Definitely', 'Probably', 'Maybe', 'Not sure yet'],
            'duration': 60
        }
    ]

    # Topic-based poll templates
    TECH_POLLS = [
        {
            'question': 'Which technology are you most interested in?',
            'options': ['AI/ML', 'Cloud Infrastructure', 'Data Engineering', 'DevOps'],
            'duration': 90
        },
        {
            'question': 'What\'s your primary role?',
            'options': ['Developer', 'Architect', 'Data Scientist', 'Engineering Manager'],
            'duration': 75
        }
    ]

    def __init__(self):
        """Initialize poll intervention strategy"""
        self.logger = logging.getLogger(__name__)
        self.used_polls: Dict[str, List[str]] = {}  # Track used polls per session

    def generate_poll(
        self,
        session_id: str,
        event_id: str,
        poll_type: str,
        context: Dict[str, Any]
    ) -> Optional[PollQuestion]:
        """
        Generate a poll question for an intervention.

        Args:
            session_id: Session identifier
            event_id: Event identifier
            poll_type: Type of poll to generate (quick_pulse, opinion, engaging)
            context: Additional context (topic, duration, etc.)

        Returns:
            PollQuestion or None if generation fails
        """
        self.logger.info(f"🎯 Generating {poll_type} poll for session {session_id[:8]}...")

        # Select poll template based on type
        if poll_type == 'quick_pulse':
            templates = self.QUICK_PULSE_POLLS
        elif poll_type == 'opinion':
            templates = self.OPINION_POLLS
        elif poll_type == 'engaging':
            templates = self.ENGAGING_POLLS
        else:
            self.logger.warning(f"Unknown poll type: {poll_type}, using quick_pulse")
            templates = self.QUICK_PULSE_POLLS

        # Filter out recently used polls
        available_templates = self._filter_used_polls(session_id, templates)

        if not available_templates:
            self.logger.warning(f"All {poll_type} polls used for session {session_id}, reusing")
            available_templates = templates
            # Reset used polls for this type
            if session_id in self.used_polls:
                self.used_polls[session_id] = []

        # Select random poll from available templates
        template = random.choice(available_templates)

        # Mark as used
        self._mark_poll_used(session_id, template['question'])

        # Create poll question
        poll = PollQuestion(
            question=template['question'],
            options=template['options'],
            poll_type='MULTIPLE_CHOICE',
            duration=template['duration'],
            reason=f"Generated for {poll_type} intervention",
            context={
                'session_id': session_id,
                'event_id': event_id,
                'template_type': poll_type,
                'generated_at': datetime.utcnow().isoformat()
            }
        )

        self.logger.info(
            f"✅ Generated poll: '{poll.question[:50]}...' "
            f"({len(poll.options)} options, {poll.duration}s)"
        )

        return poll

    def generate_contextual_poll(
        self,
        session_id: str,
        event_id: str,
        session_context: Dict[str, Any],
        anomaly_context: Dict[str, Any]
    ) -> Optional[PollQuestion]:
        """
        Generate a poll that's contextually relevant to the session and anomaly.

        Args:
            session_id: Session identifier
            event_id: Event identifier
            session_context: Session metadata (topic, speaker, etc.)
            anomaly_context: Anomaly details (type, signals, etc.)

        Returns:
            PollQuestion or None
        """
        # Check if we have topic information
        topic = session_context.get('topic', '').lower()

        # If tech-related, use tech polls
        tech_keywords = ['ai', 'ml', 'cloud', 'data', 'devops', 'engineering', 'software']
        if any(keyword in topic for keyword in tech_keywords):
            templates = self.TECH_POLLS + self.OPINION_POLLS
        else:
            # Default to engaging polls for unknown topics
            templates = self.ENGAGING_POLLS

        # Filter and select
        available_templates = self._filter_used_polls(session_id, templates)
        if not available_templates:
            available_templates = templates

        template = random.choice(available_templates)
        self._mark_poll_used(session_id, template['question'])

        return PollQuestion(
            question=template['question'],
            options=template['options'],
            poll_type='MULTIPLE_CHOICE',
            duration=template['duration'],
            reason="Contextually generated based on session topic",
            context={
                'session_id': session_id,
                'event_id': event_id,
                'topic': topic,
                'contextual': True,
                'generated_at': datetime.utcnow().isoformat()
            }
        )

    def generate_crisis_poll(
        self,
        session_id: str,
        event_id: str,
        crisis_type: str
    ) -> Optional[PollQuestion]:
        """
        Generate a poll for crisis situations (mass exit, critical low engagement).

        Args:
            session_id: Session identifier
            event_id: Event identifier
            crisis_type: Type of crisis (mass_exit, critical_low, etc.)

        Returns:
            PollQuestion designed to re-engage and diagnose issue
        """
        if crisis_type == 'mass_exit':
            return PollQuestion(
                question='Before you go, what could make this session better?',
                options=[
                    'More interactive content',
                    'Different pace',
                    'More practical examples',
                    'Technical difficulties'
                ],
                poll_type='MULTIPLE_CHOICE',
                duration=45,
                reason='Mass exit crisis intervention',
                context={
                    'session_id': session_id,
                    'event_id': event_id,
                    'crisis_type': crisis_type,
                    'priority': 'HIGH'
                }
            )
        elif crisis_type == 'critical_low':
            return PollQuestion(
                question='Quick check: Are you still with us?',
                options=['Yes, paying attention', 'Yes, multitasking', 'Taking a break', 'About to leave'],
                poll_type='MULTIPLE_CHOICE',
                duration=45,
                reason='Critical low engagement intervention',
                context={
                    'session_id': session_id,
                    'event_id': event_id,
                    'crisis_type': crisis_type,
                    'priority': 'HIGH'
                }
            )
        else:
            # Fallback to generic crisis poll
            return PollQuestion(
                question='How can we improve your experience right now?',
                options=['Change topic', 'More interaction', 'Slow down', 'Speed up'],
                poll_type='MULTIPLE_CHOICE',
                duration=60,
                reason='Generic crisis intervention',
                context={
                    'session_id': session_id,
                    'event_id': event_id,
                    'crisis_type': crisis_type
                }
            )

    def _filter_used_polls(
        self,
        session_id: str,
        templates: List[Dict]
    ) -> List[Dict]:
        """
        Filter out polls that have been recently used in this session.

        Args:
            session_id: Session identifier
            templates: List of poll templates

        Returns:
            Filtered list of templates
        """
        if session_id not in self.used_polls:
            return templates

        used_questions = self.used_polls[session_id]

        return [
            template for template in templates
            if template['question'] not in used_questions
        ]

    def _mark_poll_used(self, session_id: str, question: str):
        """
        Mark a poll as used for a session.

        Args:
            session_id: Session identifier
            question: Poll question text
        """
        if session_id not in self.used_polls:
            self.used_polls[session_id] = []

        self.used_polls[session_id].append(question)

        # Keep only last 10 used polls to allow reuse after a while
        if len(self.used_polls[session_id]) > 10:
            self.used_polls[session_id] = self.used_polls[session_id][-10:]

    async def generate_with_ai(
        self,
        session_id: str,
        event_id: str,
        anomaly_type: str,
        session_context: Dict[str, Any],
        signals: Dict[str, Any],
        use_llm: bool = True
    ) -> Optional[PollQuestion]:
        """
        Generate poll using AI (Phase 4) with fallback to templates.

        Args:
            session_id: Session identifier
            event_id: Event identifier
            anomaly_type: Type of anomaly (SUDDEN_DROP, etc.)
            session_context: Session metadata
            signals: Current engagement signals
            use_llm: Whether to try LLM generation (default True)

        Returns:
            PollQuestion generated by AI or templates
        """
        # Try LLM generation if enabled
        if use_llm:
            try:
                from app.agents.content_generator import content_generator

                self.logger.info(f"🤖 Attempting AI poll generation for {anomaly_type}")

                result = await content_generator.generate_poll(
                    session_id=session_id,
                    event_id=event_id,
                    anomaly_type=anomaly_type,
                    session_context=session_context,
                    signals=signals
                )

                poll = result['poll']
                method = result['generation_method']

                if method in ['sonnet', 'haiku']:
                    self.logger.info(f"✅ AI-generated poll using {method}")
                    # Mark the question as used
                    self._mark_poll_used(session_id, poll.question)
                    return poll

            except Exception as e:
                self.logger.warning(f"AI generation failed: {e}, falling back to templates")

        # Fallback to template generation
        self.logger.info("📚 Using template-based generation")
        poll_type = self._anomaly_to_poll_type(anomaly_type)

        return self.generate_poll(
            session_id=session_id,
            event_id=event_id,
            poll_type=poll_type,
            context={'anomaly_type': anomaly_type}
        )

    def _anomaly_to_poll_type(self, anomaly_type: str) -> str:
        """Map anomaly type to template poll type"""
        mapping = {
            'SUDDEN_DROP': 'quick_pulse',
            'GRADUAL_DECLINE': 'opinion',
            'LOW_ENGAGEMENT': 'engaging',
            'MASS_EXIT': 'quick_pulse'
        }
        return mapping.get(anomaly_type, 'engaging')

    def cleanup_session(self, session_id: str):
        """
        Clean up poll state for a session.

        Args:
            session_id: Session identifier
        """
        if session_id in self.used_polls:
            del self.used_polls[session_id]
        self.logger.info(f"🧹 Cleaned up poll strategy for session {session_id}")


# Global instance
poll_strategy = PollInterventionStrategy()
