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
from app.core.circuit_breaker import CircuitBreakerError

logger = logging.getLogger(__name__)

# Template fallbacks for chat prompts
# Keys match thompson_sampling.AnomalyType enum: SUDDEN_DROP, GRADUAL_DECLINE, LOW_ENGAGEMENT, MASS_EXIT
CHAT_PROMPT_TEMPLATES = {
    "SUDDEN_DROP": [
        "What's one thing you'd love to explore deeper in this session?",
        "Quick poll: What's been your biggest insight so far? Share below!",
        "Let's hear from you! What questions are on your mind right now?",
        "We'd love to hear your perspective - what resonates most with you?",
    ],
    "GRADUAL_DECLINE": [
        "Don't be shy! Drop an emoji if you're finding this valuable!",
        "Type your biggest takeaway so far - we want to hear from everyone!",
        "Quick check-in: How are you feeling about today's session? 1-10?",
        "Share one word that describes this session for you!",
    ],
    "LOW_ENGAGEMENT": [
        "We hear you! What would make this session more valuable for you?",
        "Your feedback matters - what topics should we dig into more?",
        "Let's reset: What's the ONE thing you want to walk away with today?",
    ],
    "MASS_EXIT": [
        "Before you go - what's ONE thing we could do differently?",
        "We value your time! Quick question: what brought you here today?",
        "Help us improve! What topic would make you stay longer?",
    ],
    "default": [
        "What's on your mind? Share your thoughts in the chat!",
        "We'd love to hear from you - drop a comment below!",
        "Let's make this interactive! What questions do you have?",
    ],
}

# Template fallbacks for notifications
# Keys match thompson_sampling.AnomalyType enum: SUDDEN_DROP, GRADUAL_DECLINE, LOW_ENGAGEMENT, MASS_EXIT
NOTIFICATION_TEMPLATES = {
    "SUDDEN_DROP": {
        "title": "Engagement Alert: Sudden Drop Detected",
        "body": "Engagement has dropped suddenly in {session_name}. Immediate intervention recommended.",
        "priority": "high",
        "suggested_action": "Launch a poll or chat prompt to re-engage audience",
    },
    "GRADUAL_DECLINE": {
        "title": "Participation Gradually Declining",
        "body": "Active participation is steadily decreasing in {session_name}.",
        "priority": "medium",
        "suggested_action": "Launch a quick poll or gamification challenge",
    },
    "LOW_ENGAGEMENT": {
        "title": "Low Engagement Detected",
        "body": "Engagement remains persistently low in {session_name}.",
        "priority": "medium",
        "suggested_action": "Consider changing pace or launching interactive content",
    },
    "MASS_EXIT": {
        "title": "Critical: Users Leaving Session",
        "body": "Multiple users are leaving {session_name}. Urgent intervention needed.",
        "priority": "high",
        "suggested_action": "Immediate action required - poll or direct engagement",
    },
    "default": {
        "title": "Session Alert",
        "body": "An anomaly was detected in {session_name}.",
        "priority": "medium",
        "suggested_action": "Review session metrics",
    },
}

# Template fallbacks for gamification
# Keys match thompson_sampling.AnomalyType enum: SUDDEN_DROP, GRADUAL_DECLINE, LOW_ENGAGEMENT, MASS_EXIT
GAMIFICATION_TEMPLATES = {
    "SUDDEN_DROP": {
        "type": "challenge",
        "name": "Conversation Starter",
        "description": "Be one of the first 5 to ask a question!",
        "icon": "lightning",
        "points": 50,
        "trigger_condition": "First 5 users to send a message",
    },
    "GRADUAL_DECLINE": {
        "type": "achievement",
        "name": "Active Participant",
        "description": "Share your thoughts in the chat",
        "icon": "star",
        "points": 25,
        "trigger_condition": "User sends a chat message",
    },
    "LOW_ENGAGEMENT": {
        "type": "badge",
        "name": "Constructive Voice",
        "description": "Share constructive feedback with the community",
        "icon": "heart",
        "points": 30,
        "trigger_condition": "User provides feedback",
    },
    "MASS_EXIT": {
        "type": "challenge",
        "name": "Stay & Win",
        "description": "Complete this session for bonus rewards!",
        "icon": "crown",
        "points": 75,
        "trigger_condition": "User remains until session end",
    },
    "default": {
        "type": "achievement",
        "name": "Engaged Attendee",
        "description": "Thanks for being an active participant!",
        "icon": "trophy",
        "points": 20,
        "trigger_condition": "User participates in session",
    },
}


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

    # System prompt for chat prompts
    CHAT_PROMPT_SYSTEM_PROMPT = """You are an expert engagement facilitator for live events.

Your task is to generate contextual chat prompts that re-engage audiences during live sessions.

CONTEXT:
- You're helping a session that's experiencing engagement issues
- The chat prompt should feel natural, not robotic
- Consider the session context and anomaly type when crafting the message

OUTPUT FORMAT (JSON):
{
  "message": "The chat message to send (50-150 characters)",
  "tone": "friendly|curious|encouraging|energetic",
  "call_to_action": "What you want the audience to do"
}

GUIDELINES:
1. Be conversational and authentic - avoid corporate speak
2. Ask open-ended questions that invite participation
3. Reference the session topic when possible
4. Create a sense of community ("we", "us", "together")
5. Keep messages concise - chat moves fast
6. Match tone to the situation (serious topics = thoughtful, fun topics = energetic)

ANOMALY-SPECIFIC APPROACHES:
- SUDDEN_DROP: Ask a thought-provoking question to immediately recapture attention
- GRADUAL_DECLINE: Invite specific actions ("Type your biggest takeaway!")
- LOW_ENGAGEMENT: Acknowledge the moment, try a fresh angle to draw people in
- MASS_EXIT: Create urgency and value ("Don't miss what's coming next!")

Important: Return ONLY the JSON object, no additional text or explanation."""

    # System prompt for notifications
    NOTIFICATION_SYSTEM_PROMPT = """You are an expert at crafting compelling event notifications.

Your task is to generate notification content that captures attention and drives action.

CONTEXT:
- Notifications appear in the organizer dashboard
- They should be informative but also actionable
- Organizers need to quickly understand what's happening and what to do

OUTPUT FORMAT (JSON):
{
  "title": "Short attention-grabbing title (max 60 chars)",
  "body": "Detailed notification message (max 200 chars)",
  "priority": "high|medium|low",
  "suggested_action": "What the organizer should consider doing"
}

GUIDELINES:
1. Lead with the most important information
2. Be specific about what's happening and where
3. Include numbers/metrics when relevant
4. Suggest actionable next steps
5. Don't be alarmist - be informative
6. Use clear, professional language

ANOMALY-SPECIFIC APPROACHES:
- SUDDEN_DROP: Urgent tone, focus on immediate action needed
- GRADUAL_DECLINE: Warning tone, highlight the trend and suggest intervention
- LOW_ENGAGEMENT: Informative tone, suggest content or pacing changes
- MASS_EXIT: Critical tone, emphasize urgency and potential causes

Important: Return ONLY the JSON object, no additional text or explanation."""

    # System prompt for gamification
    GAMIFICATION_SYSTEM_PROMPT = """You are an expert at designing engaging gamification elements for live events.

Your task is to generate contextual achievements, challenges, or rewards that boost engagement.

CONTEXT:
- Gamification should feel earned, not forced
- Elements should tie into the session content when possible
- Consider the current engagement state when designing

OUTPUT FORMAT (JSON):
{
  "type": "achievement|challenge|badge|reward",
  "name": "Short catchy name (max 30 chars)",
  "description": "What the user needs to do or has done (max 100 chars)",
  "icon": "trophy|star|fire|lightning|heart|crown|rocket|gem",
  "points": 10-100,
  "trigger_condition": "When this should be awarded/activated"
}

GUIDELINES:
1. Make achievements feel meaningful, not trivial
2. Challenges should be achievable within the session
3. Names should be fun and memorable
4. Tie into session themes when possible
5. Vary the difficulty and point values
6. Create FOMO without being manipulative

ANOMALY-SPECIFIC APPROACHES:
- SUDDEN_DROP: Challenge to spark immediate participation ("First to ask a question!")
- GRADUAL_DECLINE: Reward small actions to rebuild momentum gradually
- LOW_ENGAGEMENT: Achievement for any participation to encourage involvement
- MASS_EXIT: High-value reward for staying ("Complete the session for bonus!")

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

    # =====================
    # Generic LLM Generation
    # =====================

    async def _generate_content_with_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        content_type: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate content using LLM with Sonnet → Haiku fallback.

        Args:
            system_prompt: The system prompt for the content type
            user_prompt: The user prompt with context
            content_type: Type of content being generated (for logging)

        Returns:
            Dict with 'content', 'method', 'metadata' or None if all attempts fail
        """
        if not self.client:
            return None

        try:
            result = await self.client.generate_with_fallback(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                primary_model=LLMClient.SONNET_4_5,
                fallback_model=LLMClient.HAIKU,
                max_tokens=500,
                temperature=0.7,
                use_cache=True,
                timeout=5.0
            )

            # Parse JSON response
            content = self._parse_json_response(result['text'])
            if content:
                method = 'haiku' if result.get('fallback_used') else 'sonnet'
                return {
                    'content': content,
                    'method': method,
                    'metadata': {
                        'model': result.get('model'),
                        'tokens_in': result.get('tokens_input'),
                        'tokens_out': result.get('tokens_output'),
                        'latency_ms': result.get('latency_ms'),
                        'content_type': content_type,
                        'fallback_used': result.get('fallback_used', False),
                    },
                }

        except CircuitBreakerError:
            self.logger.warning(f"Circuit breaker open for {content_type} generation")
        except Exception as e:
            self.logger.error(f"LLM generation error for {content_type}: {e}")

        return None

    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Parse JSON from LLM response, handling cases where LLM adds extra text.

        Args:
            text: Raw LLM response text

        Returns:
            Parsed JSON dict or None if parsing fails
        """
        import re

        text = text.strip()

        # Try direct parsing first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in response
        try:
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

        # Try to find nested JSON object
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    # =====================
    # Chat Prompt Generation
    # =====================

    async def generate_chat_prompt(
        self,
        session_context: Dict[str, Any],
        anomaly_type: str,
        engagement_score: float,
        recent_messages: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Generate a contextual chat prompt to re-engage the audience.

        Uses 3-layer fallback: Sonnet → Haiku → Templates

        Args:
            session_context: Session metadata (name, topic, speaker, etc.)
            anomaly_type: Type of anomaly detected
            engagement_score: Current engagement score (0-1)
            recent_messages: Optional list of recent chat messages for context

        Returns:
            Dict with 'chat_prompt', 'generation_method', 'metadata'
        """
        self.logger.info(f"💬 Generating chat prompt for {anomaly_type}")

        user_prompt = self._build_chat_prompt_user_prompt(
            session_context, anomaly_type, engagement_score, recent_messages
        )

        try:
            result = await self._generate_content_with_llm(
                system_prompt=self.CHAT_PROMPT_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                content_type="chat_prompt",
            )

            if result:
                self.logger.info(
                    f"✅ Chat prompt generated via {result['method']}: "
                    f"'{result['content'].get('message', '')[:50]}...'"
                )
                return {
                    "chat_prompt": result["content"],
                    "generation_method": result["method"],
                    "metadata": result["metadata"],
                }

        except Exception as e:
            self.logger.warning(f"LLM generation failed for chat_prompt: {e}")

        # Fallback to templates
        self.logger.info("📚 Using chat prompt template (fallback)")
        template = self._get_chat_prompt_template(anomaly_type)
        return {
            "chat_prompt": {
                "message": template,
                "tone": "friendly",
                "call_to_action": "Engage with the session",
            },
            "generation_method": "template",
            "metadata": {"anomaly_type": anomaly_type, "fallback_reason": "llm_unavailable"},
        }

    def _build_chat_prompt_user_prompt(
        self,
        session_context: Dict[str, Any],
        anomaly_type: str,
        engagement_score: float,
        recent_messages: Optional[list] = None,
    ) -> str:
        """Build the user prompt for chat prompt generation."""
        messages_context = ""
        if recent_messages:
            messages_context = "\nRecent chat messages:\n" + "\n".join(
                f"- {msg}" for msg in recent_messages[-5:]
            )

        return f"""Generate a chat prompt for this session:

SESSION CONTEXT:
- Name: {session_context.get('name', 'Live Session')}
- Topic: {session_context.get('topic', 'General')}
- Speaker: {session_context.get('speaker', 'Presenter')}
- Duration so far: {session_context.get('duration_minutes', 0)} minutes
- Attendee count: {session_context.get('attendee_count', 0)}

ENGAGEMENT STATE:
- Anomaly type: {anomaly_type}
- Current engagement score: {engagement_score:.2f} (0-1 scale)
- Trend: {'declining' if engagement_score < 0.5 else 'stable' if engagement_score < 0.7 else 'strong'}
{messages_context}

Generate a natural, engaging chat prompt that addresses the {anomaly_type} situation."""

    def _get_chat_prompt_template(self, anomaly_type: str) -> str:
        """Get a random template for the given anomaly type."""
        import random
        templates = CHAT_PROMPT_TEMPLATES.get(anomaly_type, CHAT_PROMPT_TEMPLATES["default"])
        return random.choice(templates)

    # =====================
    # Notification Generation
    # =====================

    async def generate_notification(
        self,
        session_context: Dict[str, Any],
        anomaly_type: str,
        engagement_score: float,
        intervention_history: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Generate notification content for organizer dashboard.

        Uses 3-layer fallback: Sonnet → Haiku → Templates

        Args:
            session_context: Session metadata
            anomaly_type: Type of anomaly detected
            engagement_score: Current engagement score
            intervention_history: Recent interventions for context

        Returns:
            Dict with 'notification', 'generation_method', 'metadata'
        """
        self.logger.info(f"🔔 Generating notification for {anomaly_type}")

        user_prompt = self._build_notification_user_prompt(
            session_context, anomaly_type, engagement_score, intervention_history
        )

        try:
            result = await self._generate_content_with_llm(
                system_prompt=self.NOTIFICATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                content_type="notification",
            )

            if result:
                self.logger.info(
                    f"✅ Notification generated via {result['method']}: "
                    f"'{result['content'].get('title', '')[:50]}...'"
                )
                return {
                    "notification": result["content"],
                    "generation_method": result["method"],
                    "metadata": result["metadata"],
                }

        except Exception as e:
            self.logger.warning(f"LLM generation failed for notification: {e}")

        # Fallback to templates
        self.logger.info("📚 Using notification template (fallback)")
        template = self._get_notification_template(anomaly_type, session_context)
        return {
            "notification": template,
            "generation_method": "template",
            "metadata": {"anomaly_type": anomaly_type, "fallback_reason": "llm_unavailable"},
        }

    def _build_notification_user_prompt(
        self,
        session_context: Dict[str, Any],
        anomaly_type: str,
        engagement_score: float,
        intervention_history: Optional[list] = None,
    ) -> str:
        """Build the user prompt for notification generation."""
        history_context = ""
        if intervention_history:
            history_context = "\nRecent interventions:\n" + "\n".join(
                f"- {h.get('type', 'unknown')} at {h.get('timestamp', 'unknown')}"
                for h in intervention_history[-3:]
            )

        severity = 'Critical' if engagement_score < 0.3 else 'Warning' if engagement_score < 0.5 else 'Info'

        return f"""Generate a notification for the event organizer:

SESSION CONTEXT:
- Name: {session_context.get('name', 'Live Session')}
- Topic: {session_context.get('topic', 'General')}
- Attendee count: {session_context.get('attendee_count', 0)}

ANOMALY DETAILS:
- Type: {anomaly_type}
- Engagement score: {engagement_score:.2f} (0-1 scale)
- Severity: {severity}
{history_context}

Generate a clear, actionable notification for the organizer."""

    def _get_notification_template(
        self, anomaly_type: str, session_context: Dict[str, Any]
    ) -> Dict[str, str]:
        """Get template notification for the given anomaly type."""
        template = NOTIFICATION_TEMPLATES.get(anomaly_type, NOTIFICATION_TEMPLATES["default"]).copy()
        session_name = session_context.get("name", "the session")
        template["body"] = template["body"].format(session_name=session_name)
        return template

    # =====================
    # Gamification Generation
    # =====================

    async def generate_gamification(
        self,
        session_context: Dict[str, Any],
        anomaly_type: str,
        engagement_score: float,
        existing_achievements: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Generate gamification content (achievement, challenge, badge).

        Uses 3-layer fallback: Sonnet → Haiku → Templates

        Args:
            session_context: Session metadata
            anomaly_type: Type of anomaly detected
            engagement_score: Current engagement score
            existing_achievements: Already awarded achievements to avoid duplicates

        Returns:
            Dict with 'gamification', 'generation_method', 'metadata'
        """
        self.logger.info(f"🎮 Generating gamification for {anomaly_type}")

        user_prompt = self._build_gamification_user_prompt(
            session_context, anomaly_type, engagement_score, existing_achievements
        )

        try:
            result = await self._generate_content_with_llm(
                system_prompt=self.GAMIFICATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                content_type="gamification",
            )

            if result:
                self.logger.info(
                    f"✅ Gamification generated via {result['method']}: "
                    f"'{result['content'].get('name', '')[:30]}...'"
                )
                return {
                    "gamification": result["content"],
                    "generation_method": result["method"],
                    "metadata": result["metadata"],
                }

        except Exception as e:
            self.logger.warning(f"LLM generation failed for gamification: {e}")

        # Fallback to templates
        self.logger.info("📚 Using gamification template (fallback)")
        template = self._get_gamification_template(anomaly_type)
        return {
            "gamification": template,
            "generation_method": "template",
            "metadata": {"anomaly_type": anomaly_type, "fallback_reason": "llm_unavailable"},
        }

    def _build_gamification_user_prompt(
        self,
        session_context: Dict[str, Any],
        anomaly_type: str,
        engagement_score: float,
        existing_achievements: Optional[list] = None,
    ) -> str:
        """Build the user prompt for gamification generation."""
        existing_context = ""
        if existing_achievements:
            existing_context = "\nAlready awarded in this session (avoid duplicates):\n" + "\n".join(
                f"- {a}" for a in existing_achievements
            )

        goal = 'Re-engage audience' if engagement_score < 0.5 else 'Maintain momentum'

        return f"""Generate a gamification element for this session:

SESSION CONTEXT:
- Name: {session_context.get('name', 'Live Session')}
- Topic: {session_context.get('topic', 'General')}
- Duration so far: {session_context.get('duration_minutes', 0)} minutes
- Attendee count: {session_context.get('attendee_count', 0)}

ENGAGEMENT STATE:
- Anomaly type: {anomaly_type}
- Current engagement score: {engagement_score:.2f}
- Goal: {goal}
{existing_context}

Generate a gamification element that addresses the {anomaly_type} situation."""

    def _get_gamification_template(self, anomaly_type: str) -> Dict[str, Any]:
        """Get template gamification for the given anomaly type."""
        return GAMIFICATION_TEMPLATES.get(anomaly_type, GAMIFICATION_TEMPLATES["default"]).copy()


# Global instance
content_generator = ContentGenerator()
