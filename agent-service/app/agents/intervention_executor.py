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
from app.agents.content_generator import content_generator
from app.db.models import Intervention
from app.core.redis_client import RedisClient
from app.core.config import get_settings
from app.core.event_settings import get_notification_service
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
        from app.core import redis_client as redis_module
        if redis_module.redis_client is None:
            raise RuntimeError(
                "Redis client not initialized. Either pass redis_client to constructor "
                "or ensure global redis_client is initialized before use."
            )
        return redis_module.redis_client

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
        elif recommendation.intervention_type == 'BROADCAST':
            result = await self._execute_broadcast(recommendation, db_session)
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

        # Publish to in-app notification bell on successful execution
        if result.get('success'):
            try:
                notification_service = get_notification_service()
                await notification_service.notify_intervention_executed(
                    event_id=recommendation.context['event_id'],
                    session_id=recommendation.context['session_id'],
                    intervention_type=recommendation.intervention_type,
                    confidence=recommendation.confidence,
                    auto_approved=recommendation.context.get('auto_approved', False),
                )
            except CircuitBreakerError as e:
                # CRIT-2 FIX: Don't fail intervention if Redis publish fails
                self.logger.warning(f"Redis circuit breaker open during notification: {e.message}")
            except Exception as e:
                # Don't fail the intervention if notification fails
                self.logger.warning(f"Failed to publish intervention notification: {e}")

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
                extra_data={
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

    async def _execute_broadcast(
        self,
        recommendation: InterventionRecommendation,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Execute a broadcast intervention using AI-generated content.

        Args:
            recommendation: Intervention recommendation
            db_session: Database session

        Returns:
            Execution result
        """
        try:
            session_id = recommendation.context['session_id']
            event_id = recommendation.context['event_id']
            anomaly_type = recommendation.context.get('anomaly_type', 'SUDDEN_DROP')
            engagement_score = recommendation.context.get('engagement_score', 0.5)

            # Build session context for content generation
            session_context = {
                "name": recommendation.context.get("session_name", "Live Session"),
                "topic": recommendation.context.get("topic", "General"),
                "speaker": recommendation.context.get("speaker", "Presenter"),
                "duration_minutes": recommendation.context.get("duration_minutes", 0),
                "attendee_count": recommendation.context.get("attendee_count", 0),
            }

            # Get recent messages for context (if available)
            recent_messages = recommendation.context.get("recent_messages", [])

            # Generate broadcast message using ContentGenerator (AI with fallback)
            result = await content_generator.generate_broadcast(
                session_context=session_context,
                anomaly_type=anomaly_type,
                engagement_score=engagement_score,
            )

            broadcast = result["broadcast"]
            message_text = broadcast.get("message") if isinstance(broadcast, dict) else broadcast
            generation_method = result["generation_method"]

            # Create intervention record
            intervention_id = str(uuid.uuid4())
            intervention = Intervention(
                id=uuid.UUID(intervention_id),
                session_id=uuid.UUID(session_id),
                timestamp=datetime.now(timezone.utc),
                type='BROADCAST',
                confidence=recommendation.confidence,
                reasoning=recommendation.reason,
                extra_data={
                    'message': message_text,
                    'broadcast_data': chat_prompt if isinstance(chat_prompt, dict) else None,
                    'generation_method': generation_method,
                    'anomaly_type': anomaly_type,
                    'estimated_impact': recommendation.estimated_impact,
                    'priority': recommendation.priority
                }
            )

            db_session.add(intervention)
            await db_session.commit()

            # Publish broadcast intervention to Redis
            await self._publish_broadcast_intervention(
                intervention_id=intervention_id,
                session_id=session_id,
                event_id=event_id,
                message=message_text
            )

            self.logger.info(
                f"Broadcast intervention executed via {generation_method}: '{message_text[:50]}...'"
            )

            return {
                'success': True,
                'intervention_id': intervention_id,
                'message': message_text,
                'generation_method': generation_method
            }

        except Exception as e:
            self.logger.error(f"Failed to execute broadcast: {e}", exc_info=True)
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
        Execute a notification intervention using AI-generated content.

        Args:
            recommendation: Intervention recommendation
            db_session: Database session

        Returns:
            Execution result
        """
        try:
            session_id = recommendation.context['session_id']
            event_id = recommendation.context['event_id']
            anomaly_type = recommendation.context.get('anomaly_type', 'SUDDEN_DROP')
            engagement_score = recommendation.context.get('engagement_score', 0.5)

            # Build session context for content generation
            session_context = {
                "name": recommendation.context.get("session_name", "Live Session"),
                "topic": recommendation.context.get("topic", "General"),
                "attendee_count": recommendation.context.get("attendee_count", 0),
            }

            # Get recent interventions for context
            intervention_history = recommendation.context.get("intervention_history", [])

            # Generate notification using ContentGenerator (AI with fallback)
            result = await content_generator.generate_notification(
                session_context=session_context,
                anomaly_type=anomaly_type,
                engagement_score=engagement_score,
                intervention_history=intervention_history,
            )

            notification = result["notification"]
            generation_method = result["generation_method"]

            # Create intervention record
            intervention_id = str(uuid.uuid4())
            intervention = Intervention(
                id=uuid.UUID(intervention_id),
                session_id=uuid.UUID(session_id),
                timestamp=datetime.now(timezone.utc),
                type='NOTIFICATION',
                confidence=recommendation.confidence,
                reasoning=recommendation.reason,
                extra_data={
                    'notification': notification,
                    'generation_method': generation_method,
                    'anomaly_type': anomaly_type,
                    'target': recommendation.context.get('target', 'organizer'),
                    'escalate': recommendation.context.get('escalate', False),
                    'estimated_impact': recommendation.estimated_impact,
                    'priority': recommendation.priority
                }
            )

            db_session.add(intervention)
            await db_session.commit()

            # Publish notification to Redis with AI-generated content
            await self._publish_notification_intervention(
                intervention_id=intervention_id,
                session_id=session_id,
                event_id=event_id,
                notification_type=anomaly_type,
                target=recommendation.context.get('target'),
                escalate=recommendation.context.get('escalate', False),
                notification_content=notification
            )

            self.logger.info(
                f"✅ Notification intervention executed via {generation_method}: "
                f"'{notification.get('title', '')[:40]}...'"
            )

            return {
                'success': True,
                'intervention_id': intervention_id,
                'notification': notification,
                'generation_method': generation_method
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
        Execute a gamification intervention using AI-generated content.

        Args:
            recommendation: Intervention recommendation
            db_session: Database session

        Returns:
            Execution result
        """
        try:
            session_id = recommendation.context['session_id']
            event_id = recommendation.context['event_id']
            anomaly_type = recommendation.context.get('anomaly_type', 'SUDDEN_DROP')
            engagement_score = recommendation.context.get('engagement_score', 0.5)

            # Validate session_id as UUID
            try:
                session_uuid = uuid.UUID(session_id)
            except ValueError as e:
                return {
                    'success': False,
                    'error': f'Invalid session_id format: {e}'
                }

            # Build session context for content generation
            session_context = {
                "name": recommendation.context.get("session_name", "Live Session"),
                "topic": recommendation.context.get("topic", "General"),
                "duration_minutes": recommendation.context.get("duration_minutes", 0),
                "attendee_count": recommendation.context.get("attendee_count", 0),
            }

            # Get existing achievements to avoid duplicates
            existing_achievements = recommendation.context.get("existing_achievements", [])

            # Generate gamification using ContentGenerator (AI with fallback)
            result = await content_generator.generate_gamification(
                session_context=session_context,
                anomaly_type=anomaly_type,
                engagement_score=engagement_score,
                existing_achievements=existing_achievements,
            )

            gamification_content = result["gamification"]
            generation_method = result["generation_method"]

            # Create intervention record
            intervention_id = str(uuid.uuid4())
            intervention = Intervention(
                id=uuid.UUID(intervention_id),
                session_id=session_uuid,
                timestamp=datetime.now(timezone.utc),
                type='GAMIFICATION',
                confidence=recommendation.confidence,
                reasoning=recommendation.reason,
                extra_data={
                    'gamification': gamification_content,
                    'generation_method': generation_method,
                    'anomaly_type': anomaly_type,
                    'estimated_impact': recommendation.estimated_impact,
                    'priority': recommendation.priority
                }
            )

            db_session.add(intervention)
            await db_session.commit()

            # Publish gamification intervention to Redis
            await self._publish_gamification_intervention(
                intervention_id=intervention_id,
                session_id=session_id,
                event_id=event_id,
                content=gamification_content,
                recommendation=recommendation
            )

            # Track as pending
            self.pending_interventions[intervention_id] = {
                'type': 'GAMIFICATION',
                'session_id': session_id,
                'timestamp': datetime.now(timezone.utc),
                'recommendation': recommendation
            }

            self.logger.info(
                f"✅ Gamification intervention executed via {generation_method}: "
                f"'{gamification_content.get('name', '')}' (ID: {intervention_id[:8]}...)"
            )

            return {
                'success': True,
                'intervention_id': intervention_id,
                'gamification': gamification_content,
                'generation_method': generation_method
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
            # CRIT-2 FIX: Log but don't raise - intervention already committed to DB
            self.logger.error(f"Redis circuit breaker open, cannot publish poll intervention: {e.message}")
        except Exception as e:
            self.logger.error(f"Failed to publish poll intervention to Redis: {e}")

    async def _publish_broadcast_intervention(
        self,
        intervention_id: str,
        session_id: str,
        event_id: str,
        message: str
    ):
        """Publish broadcast intervention to Redis.

        RELIABILITY: Uses circuit breaker to prevent blocking on Redis failures.
        """
        payload = {
            'type': 'agent.intervention.broadcast',
            'intervention_id': intervention_id,
            'session_id': session_id,
            'event_id': event_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'message': message
        }

        try:
            async with redis_circuit_breaker:
                await self.redis.publish('agent.interventions', json.dumps(payload))
            self.logger.info(f"Published broadcast intervention to Redis: {intervention_id[:8]}...")
        except CircuitBreakerError as e:
            # CRIT-2 FIX: Log but don't raise - intervention already committed to DB
            self.logger.error(f"Redis circuit breaker open, cannot publish broadcast intervention: {e.message}")
        except Exception as e:
            self.logger.error(f"Failed to publish broadcast intervention to Redis: {e}")

    async def _publish_notification_intervention(
        self,
        intervention_id: str,
        session_id: str,
        event_id: str,
        notification_type: str,
        target: Optional[str],
        escalate: bool,
        notification_content: Optional[Dict[str, Any]] = None
    ):
        """Publish notification intervention to Redis.

        RELIABILITY: Uses circuit breaker to prevent blocking on Redis failures.

        Args:
            intervention_id: Unique intervention ID
            session_id: Session ID
            event_id: Event ID
            notification_type: Type of notification (anomaly type)
            target: Target audience for the notification
            escalate: Whether to escalate the notification
            notification_content: AI-generated notification content (title, body, etc.)
        """
        message = {
            'type': 'agent.intervention.notification',
            'intervention_id': intervention_id,
            'session_id': session_id,
            'event_id': event_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'notification_type': notification_type,
            'target': target,
            'escalate': escalate,
            'content': notification_content  # AI-generated notification content
        }

        try:
            async with redis_circuit_breaker:
                await self.redis.publish('agent.interventions', json.dumps(message))
            self.logger.info(f"Published notification intervention to Redis: {intervention_id[:8]}...")
        except CircuitBreakerError as e:
            # CRIT-2 FIX: Log but don't raise - intervention already committed to DB
            self.logger.error(f"Redis circuit breaker open, cannot publish notification: {e.message}")
        except Exception as e:
            self.logger.error(f"Failed to publish notification intervention to Redis: {e}")

    async def _publish_gamification_intervention(
        self,
        intervention_id: str,
        session_id: str,
        event_id: str,
        content: Dict[str, Any],
        recommendation: InterventionRecommendation
    ):
        """Publish gamification intervention to Redis.

        RELIABILITY: Uses circuit breaker to prevent blocking on Redis failures.

        Args:
            intervention_id: Unique intervention ID
            session_id: Session ID
            event_id: Event ID
            content: Gamification content dict with action, template, name, etc.
            recommendation: Original recommendation
        """
        payload = {
            'type': 'agent.intervention.gamification',
            'intervention_id': intervention_id,
            'session_id': session_id,
            'event_id': event_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'content': content,
            'metadata': {
                'reason': recommendation.reason,
                'confidence': recommendation.confidence,
                'priority': recommendation.priority,
                'estimated_impact': recommendation.estimated_impact
            }
        }

        try:
            async with redis_circuit_breaker:
                await self.redis.publish('agent.interventions', json.dumps(payload))
            self.logger.info(f"Published gamification intervention to Redis: {intervention_id[:8]}...")
        except CircuitBreakerError as e:
            # CRIT-2 FIX: Log but don't raise - intervention already committed to DB
            self.logger.error(f"Redis circuit breaker open, cannot publish gamification: {e.message}")
        except Exception as e:
            self.logger.error(f"Failed to publish gamification intervention to Redis: {e}")

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
