"""
Content Generator
AI-powered content generation for interventions using Claude Sonnet 4.5
"""
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.llm_client import llm_client, LLMClient
from app.agents.poll_intervention_strategy import poll_strategy, PollQuestion

logger = logging.getLogger(__name__)


class ContentGenerator:
    """
    Generates intervention content using LLM with multi-layer fallback.

    Fallback strategy:
    1. Claude Sonnet 4.5 (primary) - Best quality
    2. Claude Haiku (fallback) - Fast backup
    3. Template library (guaranteed) - Always works
    """

    # System prompt with caching
    SYSTEM_PROMPT = """You are an expert engagement coach helping event organizers keep their audiences engaged during live sessions.

Your task is to generate engaging poll questions that will re-capture audience attention when engagement drops.

Guidelines:
- Questions should be relevant to the session topic
- Keep questions concise (under 100 characters)
- Provide 3-4 clear answer options
- Make questions thought-provoking but easy to answer quickly
- Match the tone to the audience (technical, general, casual, formal)
- Avoid yes/no questions unless they're particularly compelling

Return your response as valid JSON with this exact structure:
{
  "question": "Your question here",
  "options": ["Option 1", "Option 2", "Option 3", "Option 4"]
}

Important: Return ONLY the JSON object, no additional text or explanation."""

    def __init__(self, client: Optional[LLMClient] = None):
        """
        Initialize content generator.

        Args:
            client: LLM client (uses global if not provided)
        """
        self.client = client or llm_client
        self.logger = logging.getLogger(__name__)

    async def generate_poll(
        self,
        session_id: str,
        event_id: str,
        anomaly_type: str,
        session_context: Dict[str, Any],
        signals: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a contextual poll question for an intervention.

        Multi-layer fallback:
        1. Try Claude Sonnet 4.5 (5s timeout)
        2. Try Claude Haiku (3s timeout)
        3. Use template library (guaranteed)

        Args:
            session_id: Session identifier
            event_id: Event identifier
            anomaly_type: Type of anomaly (SUDDEN_DROP, GRADUAL_DECLINE, etc.)
            session_context: Session metadata (topic, speaker, duration, etc.)
            signals: Current engagement signals

        Returns:
            Dict with:
                - poll: PollQuestion object
                - generation_method: 'sonnet', 'haiku', or 'template'
                - metadata: Generation details (model, tokens, latency, etc.)
        """
        self.logger.info(
            f"🎯 Generating poll for {anomaly_type} - Session: {session_id[:8]}..."
        )

        # Try LLM generation
        try:
            result = await self._generate_with_llm(
                anomaly_type=anomaly_type,
                session_context=session_context,
                signals=signals
            )

            if result:
                poll_data = result['poll_data']
                poll = PollQuestion(
                    question=poll_data['question'],
                    options=poll_data['options'],
                    poll_type='MULTIPLE_CHOICE',
                    duration=60,
                    reason=f"AI-generated for {anomaly_type}",
                    context={
                        'session_id': session_id,
                        'event_id': event_id,
                        'anomaly_type': anomaly_type,
                        'generated_at': datetime.utcnow().isoformat(),
                        'generation_method': result['method'],
                        'model': result['metadata'].get('model'),
                        'tokens': {
                            'input': result['metadata'].get('tokens_input'),
                            'output': result['metadata'].get('tokens_output'),
                            'cache_read': result['metadata'].get('tokens_cache_read'),
                            'cache_write': result['metadata'].get('tokens_cache_write'),
                        },
                        'latency_ms': result['metadata'].get('latency_ms'),
                        'fallback_used': result['metadata'].get('fallback_used', False)
                    }
                )

                self.logger.info(
                    f"✅ Poll generated via {result['method']}: '{poll.question[:50]}...' "
                    f"({result['metadata'].get('latency_ms', 0):.0f}ms)"
                )

                return {
                    'poll': poll,
                    'generation_method': result['method'],
                    'metadata': result['metadata']
                }

        except Exception as e:
            self.logger.warning(f"LLM generation failed: {e}, falling back to templates")

        # Fallback to templates (Layer 3)
        self.logger.info("📚 Using template library (final fallback)")
        poll = poll_strategy.generate_poll(
            session_id=session_id,
            event_id=event_id,
            poll_type=self._anomaly_to_poll_type(anomaly_type),
            context={'anomaly_type': anomaly_type}
        )

        return {
            'poll': poll,
            'generation_method': 'template',
            'metadata': {
                'fallback_reason': 'LLM unavailable or failed',
                'template_library_version': 'phase3'
            }
        }

    async def _generate_with_llm(
        self,
        anomaly_type: str,
        session_context: Dict[str, Any],
        signals: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate poll using LLM with fallback.

        Returns:
            Dict with poll_data, method, and metadata, or None if failed
        """
        # Build user prompt with context
        user_prompt = self._build_user_prompt(
            anomaly_type=anomaly_type,
            session_context=session_context,
            signals=signals
        )

        try:
            # Try with Sonnet → Haiku fallback
            result = await self.client.generate_with_fallback(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=user_prompt,
                primary_model=LLMClient.SONNET_4_5,
                fallback_model=LLMClient.HAIKU,
                max_tokens=500,
                temperature=0.7,
                use_cache=True,
                timeout=5.0
            )

            # Parse JSON response
            text = result['text'].strip()

            # Extract JSON from response (handle cases where LLM adds explanation)
            try:
                # Try direct parsing
                poll_data = json.loads(text)
            except json.JSONDecodeError:
                # Try to find JSON in response
                import re
                json_match = re.search(r'\{[^{}]*"question"[^{}]*"options"[^{}]*\}', text, re.DOTALL)
                if json_match:
                    poll_data = json.loads(json_match.group())
                else:
                    raise ValueError("Could not extract JSON from LLM response")

            # Validate structure
            if 'question' not in poll_data or 'options' not in poll_data:
                raise ValueError("Invalid poll structure from LLM")

            if not isinstance(poll_data['options'], list) or len(poll_data['options']) < 2:
                raise ValueError("Invalid options from LLM")

            # Determine method based on which model was used
            method = 'haiku' if result.get('fallback_used') else 'sonnet'

            return {
                'poll_data': poll_data,
                'method': method,
                'metadata': result
            }

        except Exception as e:
            self.logger.error(f"LLM generation error: {e}")
            return None

    def _build_user_prompt(
        self,
        anomaly_type: str,
        session_context: Dict[str, Any],
        signals: Dict[str, Any]
    ) -> str:
        """
        Build contextual user prompt for LLM.

        Args:
            anomaly_type: Type of anomaly detected
            session_context: Session metadata
            signals: Current engagement signals

        Returns:
            Formatted user prompt
        """
        # Extract context
        topic = session_context.get('topic', 'this session')
        duration = session_context.get('duration', 0)
        connected_users = session_context.get('connected_users', 0)

        # Format signals
        chat_rate = signals.get('chat_msgs_per_min', 0)
        active_users = signals.get('active_users', 0)
        poll_participation = signals.get('poll_participation', 0)

        # Build situation description
        situation = self._describe_situation(anomaly_type, chat_rate, active_users, poll_participation)

        prompt = f"""Session Context:
- Topic: {topic}
- Duration: {duration:.0f} seconds ({duration/60:.1f} minutes)
- Connected Users: {connected_users}

Current Engagement Signals:
- Chat: {chat_rate:.1f} messages/min
- Active Users: {active_users} participants
- Recent Poll Participation: {poll_participation*100:.0f}%

Situation:
{situation}

Generate an engaging poll question that will re-capture audience attention and get them participating again. The question should be relevant to {topic} and appropriate for the situation."""

        return prompt

    def _describe_situation(
        self,
        anomaly_type: str,
        chat_rate: float,
        active_users: int,
        poll_participation: float
    ) -> str:
        """
        Describe the engagement situation for context.

        Args:
            anomaly_type: Type of anomaly
            chat_rate: Chat messages per minute
            active_users: Number of active users
            poll_participation: Poll participation rate (0-1)

        Returns:
            Human-readable situation description
        """
        if anomaly_type == 'SUDDEN_DROP':
            return (
                f"Engagement just dropped suddenly. Chat activity dropped to {chat_rate:.1f} msgs/min "
                f"and only {active_users} users are actively participating. We need an immediate "
                "attention-grabber to bring people back."
            )
        elif anomaly_type == 'GRADUAL_DECLINE':
            return (
                f"Engagement has been gradually declining. Activity is down to {chat_rate:.1f} msgs/min. "
                "The audience may be getting fatigued or losing interest. We need something to mix it up "
                "and re-energize them."
            )
        elif anomaly_type == 'LOW_ENGAGEMENT':
            return (
                f"Engagement is persistently low with only {chat_rate:.1f} msgs/min in chat. "
                "The audience seems disengaged. We need a compelling question to draw them in."
            )
        elif anomaly_type == 'MASS_EXIT':
            return (
                "Multiple users are leaving the session. This is critical. We need a last-chance "
                "question that shows we value their input and want them to stay."
            )
        else:
            return (
                f"Engagement needs improvement. Current activity: {chat_rate:.1f} msgs/min, "
                f"{active_users} active users. Generate a question to boost participation."
            )

    def _anomaly_to_poll_type(self, anomaly_type: str) -> str:
        """
        Map anomaly type to poll template category.

        Args:
            anomaly_type: Anomaly type

        Returns:
            Poll type for template fallback
        """
        mapping = {
            'SUDDEN_DROP': 'quick_pulse',
            'GRADUAL_DECLINE': 'opinion',
            'LOW_ENGAGEMENT': 'engaging',
            'MASS_EXIT': 'quick_pulse'
        }
        return mapping.get(anomaly_type, 'engaging')


# Global instance
content_generator = ContentGenerator()
