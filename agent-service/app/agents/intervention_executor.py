"""
Intervention Executor
Executes interventions and tracks their outcomes

RELIABILITY: Uses circuit breakers to prevent cascade failures from
external service outages (LLM, Redis, Database).
"""
import logging
import json
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.agents.intervention_selector import InterventionRecommendation
from app.agents.poll_intervention_strategy import poll_strategy, PollQuestion
from app.db.models import Intervention
from app.core.redis_client import RedisClient
from app.core.config import get_settings
from app.core.circuit_breaker import (
    llm_circuit_breaker,
    redis_circuit_breaker,
    database_circuit_breaker,
    CircuitBreakerError
)

logger = logging.getLogger(__name__)


def get_llm_timeout() -> int:
    """Get LLM timeout from config"""
    return get_settings().LLM_TIMEOUT_SECONDS


# LLM call timeout in seconds (kept for backwards compatibility, use get_llm_timeout() for dynamic value)
LLM_TIMEOUT_SECONDS = 30


class InterventionExecutor:
    """
    Executes interventions and tracks their outcomes.

    Phase 3 (Manual Mode): Publishes intervention requests to Redis
    Phase 4 (Full Integration): Direct integration with platform services
    """

    def __init__(self, redis_client: Optional[RedisClient] = None):
        """
        Initialize intervention executor.

        Args:
            redis_client: Redis client for publishing interventions (optional, uses global if not provided)
        """
        self._redis = redis_client
        self.logger = logging.getLogger(__name__)
        self.pending_interventions: Dict[str, Dict] = {}  # Track pending interventions

    @property
    def redis(self) -> RedisClient:
        """Get Redis client, falling back to global instance if not provided."""
        if self._redis is not None:
            return self._redis
        # Import global redis_client lazily to avoid circular imports
        from app.core.redis_client import redis_client as global_redis
        if global_redis is None:
            raise RuntimeError(
                "Redis client not initialized. Either pass redis_client to constructor "
                "or ensure global redis_client is initialized before use."
            )
        return global_redis

    async def execute(
        self,
        recommendation: InterventionRecommendation,
        db_session: AsyncSession,
        session_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute an intervention recommendation.

        Args:
            recommendation: The intervention to execute
            db_session: Database session for storing intervention
            session_context: Additional session context

        Returns:
            Execution result dictionary
        """
        self.logger.info(
            f"🎬 Executing {recommendation.intervention_type} intervention "
            f"for session {recommendation.context['session_id'][:8]}..."
        )

        # Route to appropriate executor
        if recommendation.intervention_type == 'POLL':
            result = await self._execute_poll(recommendation, db_session, session_context)
        elif recommendation.intervention_type == 'CHAT_PROMPT':
            result = await self._execute_chat_prompt(recommendation, db_session)
        elif recommendation.intervention_type == 'NOTIFICATION':
            result = await self._execute_notification(recommendation, db_session)
        elif recommendation.intervention_type == 'GAMIFICATION':
            result = await self._execute_gamification(recommendation, db_session)
        else:
            self.logger.error(f"Unknown intervention type: {recommendation.intervention_type}")
            result = {
                'success': False,
                'error': f'Unknown intervention type: {recommendation.intervention_type}'
            }

        return result

    async def _execute_poll(
        self,
        recommendation: InterventionRecommendation,
        db_session: AsyncSession,
        session_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a poll intervention.

        RELIABILITY: Uses circuit breaker for LLM calls to prevent cascade failures.

        Args:
            recommendation: Intervention recommendation
            db_session: Database session
            session_context: Additional session context

        Returns:
            Execution result
        """
        try:
            session_id = recommendation.context['session_id']
            event_id = recommendation.context['event_id']
            anomaly_type = recommendation.context.get('anomaly_type', 'SUDDEN_DROP')

            # Validate UUIDs early
            try:
                session_uuid = uuid.UUID(session_id)
            except ValueError as e:
                return {
                    'success': False,
                    'error': f'Invalid session_id format: {e}'
                }

            # Generate poll question using AI with timeout and circuit breaker
            # Falls back to template if LLM times out, fails, or circuit is open
            timeout = get_llm_timeout()
            poll = None

            # Try LLM generation with circuit breaker protection
            try:
                async with llm_circuit_breaker:
                    poll = await asyncio.wait_for(
                        poll_strategy.generate_with_ai(
                            session_id=session_id,
                            event_id=event_id,
                            anomaly_type=anomaly_type,
                            session_context=session_context or {},
                            signals=recommendation.context.get('signals', {}),
                            use_llm=True  # Enable LLM generation
                        ),
                        timeout=timeout
                    )
            except CircuitBreakerError as e:
                self.logger.warning(
                    f"LLM circuit breaker open: {e.message}, using template fallback"
                )
            except asyncio.TimeoutError:
                self.logger.warning(
                    f"LLM call timed out after {timeout}s, using template fallback"
                )

            # Fall back to template-based generation if LLM failed
            if poll is None:
                poll = await poll_strategy.generate_with_ai(
                    session_id=session_id,
                    event_id=event_id,
                    anomaly_type=anomaly_type,
                    session_context=session_context or {},
                    signals=recommendation.context.get('signals', {}),
                    use_llm=False  # Use template fallback
                )

            if not poll:
                return {
                    'success': False,
                    'error': 'Failed to generate poll question'
                }

            # Create intervention record
            intervention_id = str(uuid.uuid4())
            intervention = Intervention(
                id=uuid.UUID(intervention_id),
                session_id=session_uuid,
                timestamp=datetime.now(timezone.utc),
                type='POLL',
                confidence=recommendation.confidence,
                reasoning=recommendation.reason,
                metadata={
                    'poll_question': poll.question,
                    'poll_options': poll.options,
                    'poll_duration': poll.duration,
                    'poll_type': poll.poll_type,
                    'estimated_impact': recommendation.estimated_impact,
                    'priority': recommendation.priority,
                    'timing': recommendation.context.get('timing', 'IMMEDIATE')
                }
            )

            db_session.add(intervention)
            await db_session.commit()

            # Publish poll intervention to Redis
            # Real-time service will pick this up and create the poll
            await self._publish_poll_intervention(
                intervention_id=intervention_id,
                session_id=session_id,
                event_id=event_id,
                poll=poll,
                recommendation=recommendation
            )

            # Track as pending
            self.pending_interventions[intervention_id] = {
                'type': 'POLL',
                'session_id': session_id,
                'timestamp': datetime.now(timezone.utc),
                'recommendation': recommendation
            }

            self.logger.info(
                f"✅ Poll intervention executed: '{poll.question[:50]}...' "
                f"(ID: {intervention_id[:8]}...)"
            )

            return {
                'success': True,
                'intervention_id': intervention_id,
                'poll': {
                    'question': poll.question,
                    'options': poll.options,
                    'duration': poll.duration
                }
            }

        except Exception as e:
            self.logger.error(f"Failed to execute poll intervention: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    async def _execute_chat_prompt(
        self,
        recommendation: InterventionRecommendation,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Execute a chat prompt intervention.

        Args:
            recommendation: Intervention recommendation
            db_session: Database session

        Returns:
            Execution result
        """
        try:
            session_id = recommendation.context['session_id']
            event_id = recommendation.context['event_id']
            prompt_type = recommendation.context.get('prompt_type', 'discussion_starter')

            # Generate chat prompt based on type
            prompts = {
                'discussion_starter': [
                    "💡 Quick question: What's the most interesting thing you've learned so far?",
                    "💬 Let's discuss: What challenges are you facing with this topic?",
                    "🤔 Share your thoughts: How would you apply this in your work?",
                    "✨ What questions do you have about what we just covered?"
                ],
                'engagement_boost': [
                    "👋 Everyone still with us? Drop a reaction if you're following along!",
                    "🎯 Quick pulse check: Are you finding this valuable?",
                    "💪 Let's keep the energy up! Any questions so far?"
                ]
            }

            import random
            prompt_text = random.choice(prompts.get(prompt_type, prompts['discussion_starter']))

            # Create intervention record
            intervention_id = str(uuid.uuid4())
            intervention = Intervention(
                id=uuid.UUID(intervention_id),
                session_id=uuid.UUID(session_id),
                timestamp=datetime.now(timezone.utc),
                type='CHAT_PROMPT',
                confidence=recommendation.confidence,
                reasoning=recommendation.reason,
                metadata={
                    'prompt': prompt_text,
                    'prompt_type': prompt_type,
                    'estimated_impact': recommendation.estimated_impact,
                    'priority': recommendation.priority
                }
            )

            db_session.add(intervention)
            await db_session.commit()

            # Publish chat prompt to Redis
            await self._publish_chat_intervention(
                intervention_id=intervention_id,
                session_id=session_id,
                event_id=event_id,
                prompt=prompt_text
            )

            self.logger.info(f"✅ Chat prompt intervention executed: '{prompt_text[:50]}...'")

            return {
                'success': True,
                'intervention_id': intervention_id,
                'prompt': prompt_text
            }

        except Exception as e:
            self.logger.error(f"Failed to execute chat prompt: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    async def _execute_notification(
        self,
        recommendation: InterventionRecommendation,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Execute a notification intervention.

        Args:
            recommendation: Intervention recommendation
            db_session: Database session

        Returns:
            Execution result
        """
        try:
            session_id = recommendation.context['session_id']
            event_id = recommendation.context['event_id']
            notification_type = recommendation.context.get('notification_type', 'disengagement_nudge')

            # Create intervention record
            intervention_id = str(uuid.uuid4())
            intervention = Intervention(
                id=uuid.UUID(intervention_id),
                session_id=uuid.UUID(session_id),
                timestamp=datetime.now(timezone.utc),
                type='NOTIFICATION',
                confidence=recommendation.confidence,
                reasoning=recommendation.reason,
                metadata={
                    'notification_type': notification_type,
                    'target': recommendation.context.get('target', 'inactive_users'),
                    'escalate': recommendation.context.get('escalate', False),
                    'estimated_impact': recommendation.estimated_impact,
                    'priority': recommendation.priority
                }
            )

            db_session.add(intervention)
            await db_session.commit()

            # Publish notification request
            await self._publish_notification_intervention(
                intervention_id=intervention_id,
                session_id=session_id,
                event_id=event_id,
                notification_type=notification_type,
                target=recommendation.context.get('target'),
                escalate=recommendation.context.get('escalate', False)
            )

            self.logger.info(
                f"✅ Notification intervention executed: {notification_type} "
                f"(target: {recommendation.context.get('target')})"
            )

            return {
                'success': True,
                'intervention_id': intervention_id,
                'notification_type': notification_type
            }

        except Exception as e:
            self.logger.error(f"Failed to execute notification: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    async def _execute_gamification(
        self,
        recommendation: InterventionRecommendation,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Execute a gamification intervention.

        Args:
            recommendation: Intervention recommendation
            db_session: Database session

        Returns:
            Execution result
        """
        try:
            session_id = recommendation.context['session_id']
            event_id = recommendation.context['event_id']
            gamification_type = recommendation.context.get('gamification_type', 'achievement_unlock')

            # Create intervention record
            intervention_id = str(uuid.uuid4())
            intervention = Intervention(
                id=uuid.UUID(intervention_id),
                session_id=uuid.UUID(session_id),
                timestamp=datetime.now(timezone.utc),
                type='GAMIFICATION',
                confidence=recommendation.confidence,
                reasoning=recommendation.reason,
                metadata={
                    'gamification_type': gamification_type,
                    'estimated_impact': recommendation.estimated_impact,
                    'priority': recommendation.priority
                }
            )

            db_session.add(intervention)
            await db_session.commit()

            self.logger.info(f"✅ Gamification intervention executed: {gamification_type}")

            return {
                'success': True,
                'intervention_id': intervention_id,
                'gamification_type': gamification_type
            }

        except Exception as e:
            self.logger.error(f"Failed to execute gamification: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    async def _publish_poll_intervention(
        self,
        intervention_id: str,
        session_id: str,
        event_id: str,
        poll: PollQuestion,
        recommendation: InterventionRecommendation
    ):
        """Publish poll intervention to Redis for real-time service to execute.

        RELIABILITY: Uses circuit breaker to prevent blocking on Redis failures.
        """
        message = {
            'type': 'agent.intervention.poll',
            'intervention_id': intervention_id,
            'session_id': session_id,
            'event_id': event_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'poll': {
                'question': poll.question,
                'options': poll.options,
                'type': poll.poll_type,
                'duration': poll.duration
            },
            'metadata': {
                'reason': recommendation.reason,
                'confidence': recommendation.confidence,
                'priority': recommendation.priority,
                'estimated_impact': recommendation.estimated_impact
            }
        }

        try:
            async with redis_circuit_breaker:
                await self.redis.publish('agent.interventions', json.dumps(message))
            self.logger.info(f"Published poll intervention to Redis: {intervention_id[:8]}...")
        except CircuitBreakerError as e:
            self.logger.error(f"Redis circuit breaker open, cannot publish poll intervention: {e.message}")
            raise

    async def _publish_chat_intervention(
        self,
        intervention_id: str,
        session_id: str,
        event_id: str,
        prompt: str
    ):
        """Publish chat prompt intervention to Redis.

        RELIABILITY: Uses circuit breaker to prevent blocking on Redis failures.
        """
        message = {
            'type': 'agent.intervention.chat',
            'intervention_id': intervention_id,
            'session_id': session_id,
            'event_id': event_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'prompt': prompt
        }

        try:
            async with redis_circuit_breaker:
                await self.redis.publish('agent.interventions', json.dumps(message))
            self.logger.info(f"Published chat intervention to Redis: {intervention_id[:8]}...")
        except CircuitBreakerError as e:
            self.logger.error(f"Redis circuit breaker open, cannot publish chat intervention: {e.message}")
            raise

    async def _publish_notification_intervention(
        self,
        intervention_id: str,
        session_id: str,
        event_id: str,
        notification_type: str,
        target: Optional[str],
        escalate: bool
    ):
        """Publish notification intervention to Redis.

        RELIABILITY: Uses circuit breaker to prevent blocking on Redis failures.
        """
        message = {
            'type': 'agent.intervention.notification',
            'intervention_id': intervention_id,
            'session_id': session_id,
            'event_id': event_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'notification_type': notification_type,
            'target': target,
            'escalate': escalate
        }

        try:
            async with redis_circuit_breaker:
                await self.redis.publish('agent.interventions', json.dumps(message))
            self.logger.info(f"Published notification intervention to Redis: {intervention_id[:8]}...")
        except CircuitBreakerError as e:
            self.logger.error(f"Redis circuit breaker open, cannot publish notification: {e.message}")
            raise

    async def record_outcome(
        self,
        intervention_id: str,
        outcome: Dict[str, Any],
        db_session: AsyncSession
    ):
        """
        Record the outcome of an intervention.

        Args:
            intervention_id: ID of the intervention
            outcome: Outcome data (success, engagement_delta, etc.)
            db_session: Database session
        """
        try:
            # Fetch intervention from database
            from sqlalchemy import select
            stmt = select(Intervention).where(Intervention.id == uuid.UUID(intervention_id))
            result = await db_session.execute(stmt)
            intervention = result.scalar_one_or_none()

            if not intervention:
                self.logger.warning(f"Intervention not found: {intervention_id}")
                return

            # Update outcome
            intervention.outcome = outcome
            await db_session.commit()

            # Remove from pending
            if intervention_id in self.pending_interventions:
                del self.pending_interventions[intervention_id]

            self.logger.info(
                f"✅ Intervention outcome recorded: {intervention_id[:8]}... - "
                f"Success: {outcome.get('success', False)}"
            )

        except Exception as e:
            self.logger.error(f"Failed to record intervention outcome: {e}", exc_info=True)
