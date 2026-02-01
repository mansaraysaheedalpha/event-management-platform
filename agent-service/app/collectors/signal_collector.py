"""
Engagement Signal Collector
Subscribes to platform events via Redis and calculates engagement scores

RELIABILITY: Includes rate limiting to prevent intervention storms.
"""
import asyncio
import json
import logging
from typing import Optional, Dict
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pydantic import ValidationError

from app.core.redis_client import RedisClient
from app.core.rate_limiter import get_intervention_rate_limiter
from app.collectors.session_tracker import SessionTracker, session_tracker
from app.utils.engagement_score import EngagementScoreCalculator, EngagementSignals, engagement_calculator
from app.agents.anomaly_detector import AnomalyDetector, anomaly_detector
from app.agents.intervention_selector import intervention_selector
from app.agents.intervention_executor import InterventionExecutor
from app.db.timescale import AsyncSessionLocal
from app.db.models import EngagementMetric
from app.models.anomaly import Anomaly
from app.models.redis_events import ChatMessageEvent, PollVoteEvent, PollClosedEvent, SyncEvent
from app.orchestrator import agent_manager
from sqlalchemy import UUID

logger = logging.getLogger(__name__)


@dataclass
class CollectorMetrics:
    """Metrics for monitoring signal collector health"""
    messages_processed: int = 0
    messages_failed: int = 0
    engagement_calculations: int = 0
    engagement_calculation_errors: int = 0
    db_write_errors: int = 0
    redis_publish_errors: int = 0
    anomaly_detections: int = 0
    interventions_triggered: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    consecutive_errors: int = 0
    started_at: Optional[datetime] = None

    def record_error(self, error_type: str, error_msg: str):
        """Record an error and update metrics"""
        self.last_error = f"{error_type}: {error_msg}"
        self.last_error_time = datetime.now(timezone.utc)
        self.consecutive_errors += 1

        # Log warning if consecutive errors exceed threshold
        if self.consecutive_errors >= 5:
            logger.warning(
                f"🚨 Signal collector has {self.consecutive_errors} consecutive errors. "
                f"Last error: {self.last_error}"
            )

    def record_success(self):
        """Record a successful operation (resets consecutive error count)"""
        self.consecutive_errors = 0

    def to_dict(self) -> Dict:
        """Export metrics as dictionary"""
        return {
            "messages_processed": self.messages_processed,
            "messages_failed": self.messages_failed,
            "engagement_calculations": self.engagement_calculations,
            "engagement_calculation_errors": self.engagement_calculation_errors,
            "db_write_errors": self.db_write_errors,
            "redis_publish_errors": self.redis_publish_errors,
            "anomaly_detections": self.anomaly_detections,
            "interventions_triggered": self.interventions_triggered,
            "error_rate": self.error_rate,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "consecutive_errors": self.consecutive_errors,
            "uptime_seconds": self.uptime_seconds,
        }

    @property
    def error_rate(self) -> float:
        """Calculate error rate as percentage"""
        total = self.messages_processed + self.messages_failed
        if total == 0:
            return 0.0
        return (self.messages_failed / total) * 100

    @property
    def uptime_seconds(self) -> float:
        """Calculate uptime in seconds"""
        if not self.started_at:
            return 0.0
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()


class EngagementSignalCollector:
    """
    Collects engagement signals from Redis Streams.
    Calculates engagement scores and stores them in TimescaleDB.

    NOTE: This collector reads from Redis Streams (XREADGROUP), NOT Pub/Sub.
    The real-time-service publishes to streams using XADD.
    """

    # Redis Streams to read from (must match what real-time-service publishes to)
    CHAT_STREAM = "platform.events.chat.message.v1"
    POLL_VOTE_STREAM = "platform.events.poll.vote.v1"
    POLL_CLOSED_STREAM = "platform.events.poll.closed.v1"
    SYNC_STREAM = "sync-events"

    # Consumer group configuration
    CONSUMER_GROUP = "engagement-conductor"
    CONSUMER_NAME = "signal-collector"

    def __init__(
        self,
        redis_client: RedisClient,
        tracker: Optional[SessionTracker] = None,
        calculator: Optional[EngagementScoreCalculator] = None,
        calculation_interval: int = 5,
    ):
        """
        Initialize the signal collector.

        Args:
            redis_client: Redis client for Streams
            tracker: Session tracker (uses global if None)
            calculator: Engagement calculator (uses global if None)
            calculation_interval: Seconds between engagement calculations
        """
        self.redis = redis_client
        self.tracker = tracker or session_tracker
        self.calculator = calculator or engagement_calculator
        self.calculation_interval = calculation_interval
        self.intervention_executor = InterventionExecutor(redis_client)
        self.running = False
        self.tasks = []
        self.metrics = CollectorMetrics()

        # Track last read IDs for each stream
        self._stream_ids: Dict[str, str] = {}

    async def start(self):
        """Start collecting signals and calculating engagement"""
        if self.running:
            logger.warning("Signal collector already running")
            return

        self.running = True
        self.metrics.started_at = datetime.now(timezone.utc)
        logger.info("🚀 Starting Engagement Signal Collector...")

        # List of streams to read from
        streams = [
            self.CHAT_STREAM,
            self.POLL_VOTE_STREAM,
            self.POLL_CLOSED_STREAM,
            self.SYNC_STREAM,
        ]

        # Create consumer groups for each stream (if they don't exist)
        for stream in streams:
            await self.redis.create_consumer_group(
                stream=stream,
                group=self.CONSUMER_GROUP,
                start_id="$"  # Only read new messages from now
            )
            # Initialize stream ID for reading new messages
            self._stream_ids[stream] = ">"

        logger.info(f"📡 Set up consumer group '{self.CONSUMER_GROUP}' for {len(streams)} streams")

        # Start background tasks
        self.tasks = [
            asyncio.create_task(self._listen_to_streams()),
            asyncio.create_task(self._calculate_engagement_loop()),
            asyncio.create_task(self._cleanup_loop()),
        ]

        logger.info("✅ Signal collector started")

    async def stop(self):
        """Stop collecting signals"""
        self.running = False
        logger.info("Stopping signal collector...")

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []

        logger.info("✅ Signal collector stopped")

    def get_metrics(self) -> Dict:
        """
        Get current collector metrics for monitoring.

        Returns:
            Dictionary containing collector health metrics
        """
        return self.metrics.to_dict()

    def is_healthy(self) -> bool:
        """
        Check if the collector is healthy.

        Returns:
            True if healthy, False if there are concerning error patterns
        """
        # Unhealthy if too many consecutive errors
        if self.metrics.consecutive_errors >= 10:
            return False

        # Unhealthy if error rate exceeds 10%
        if self.metrics.error_rate > 10.0:
            return False

        return True

    async def _listen_to_streams(self):
        """
        Listen to Redis Streams and process events.
        Uses consumer groups for reliable message delivery.
        """
        logger.info("👂 Listening for platform events via Redis Streams...")

        streams_to_read = {
            self.CHAT_STREAM: ">",
            self.POLL_VOTE_STREAM: ">",
            self.POLL_CLOSED_STREAM: ">",
            self.SYNC_STREAM: ">",
        }

        try:
            while self.running:
                try:
                    # Read from streams using consumer group
                    results = await self.redis.xreadgroup_streams(
                        group=self.CONSUMER_GROUP,
                        consumer=self.CONSUMER_NAME,
                        streams=streams_to_read,
                        count=100,
                        block=1000  # Block for 1 second
                    )

                    if not results:
                        continue

                    # Process each stream's messages
                    for stream_name, messages in results:
                        for message_id, data in messages:
                            try:
                                # Parse the message data
                                event_data = self.redis.parse_stream_message(data)
                                if not event_data:
                                    continue

                                # Route to appropriate handler based on stream
                                if stream_name == self.CHAT_STREAM:
                                    await self._handle_chat_message(event_data)
                                elif stream_name == self.POLL_VOTE_STREAM:
                                    await self._handle_poll_vote(event_data)
                                elif stream_name == self.POLL_CLOSED_STREAM:
                                    await self._handle_poll_closed(event_data)
                                elif stream_name == self.SYNC_STREAM:
                                    await self._handle_sync_event(event_data)

                                # Acknowledge the message
                                await self.redis.xack(
                                    stream_name,
                                    self.CONSUMER_GROUP,
                                    message_id
                                )

                            except Exception as e:
                                logger.error(
                                    f"Error processing message {message_id} from {stream_name}: {e}",
                                    exc_info=True
                                )
                                self.metrics.consecutive_errors += 1

                except Exception as e:
                    logger.error(f"Error reading from streams: {e}", exc_info=True)
                    self.metrics.consecutive_errors += 1
                    await asyncio.sleep(1)  # Brief pause before retry

        except asyncio.CancelledError:
            logger.info("Stream listener cancelled")
        except Exception as e:
            logger.error(f"Stream listener error: {e}", exc_info=True)

    async def _handle_chat_message(self, event_data: dict):
        """
        Handle chat message event.

        Expected data format:
        {
            "sessionId": "...",
            "eventId": "...",
            "message": {...}
        }
        """
        try:
            # Validate event data with Pydantic
            event = ChatMessageEvent(**event_data)

            self.tracker.record_chat_message(event.sessionId, event.eventId)
            logger.debug(f"📨 Chat message recorded for session {event.sessionId}")

        except ValidationError as e:
            logger.warning(f"Invalid chat message event data: {e}")
            return
        except Exception as e:
            logger.error(f"Error handling chat message: {e}", exc_info=True)

    async def _handle_poll_vote(self, event_data: dict):
        """
        Handle poll vote event.

        Expected data format:
        {
            "sessionId": "...",
            "eventId": "...",
            "pollId": "...",
            "userId": "..."
        }
        """
        try:
            # Validate event data with Pydantic
            event = PollVoteEvent(**event_data)

            self.tracker.record_poll_vote(event.sessionId, event.eventId, event.pollId)
            logger.debug(f"🗳️ Poll vote recorded for session {event.sessionId}")

        except ValidationError as e:
            logger.warning(f"Invalid poll vote event data: {e}")
            return
        except Exception as e:
            logger.error(f"Error handling poll vote: {e}", exc_info=True)

    async def _handle_poll_closed(self, event_data: dict):
        """Handle poll closed event"""
        try:
            # Validate event data with Pydantic
            event = PollClosedEvent(**event_data)
            logger.debug(f"Poll closed: {event.pollId}")

        except ValidationError as e:
            logger.warning(f"Invalid poll closed event data: {e}")
            return
        except Exception as e:
            logger.error(f"Error handling poll closed: {e}", exc_info=True)

    async def _handle_sync_event(self, event_data: dict):
        """
        Handle sync events (could include user presence, reactions, etc.)

        Expected data format varies based on event type
        """
        try:
            # Validate event data with Pydantic
            event = SyncEvent(**event_data)

            # Handle different sync event types
            if event.type == "user_join":
                if event.userId:
                    self.tracker.record_user_join(event.sessionId, event.eventId, event.userId)
                    logger.debug(f"👋 User {event.userId} joined session {event.sessionId}")

            elif event.type == "user_leave":
                if event.userId:
                    self.tracker.record_user_leave(event.sessionId, event.eventId, event.userId)
                    logger.debug(f"👋 User {event.userId} left session {event.sessionId}")

            elif event.type == "reaction":
                self.tracker.record_reaction(event.sessionId, event.eventId)
                logger.debug(f"❤️ Reaction recorded for session {event.sessionId}")

        except ValidationError as e:
            logger.warning(f"Invalid sync event data: {e}")
            return
        except Exception as e:
            logger.error(f"Error handling sync event: {e}", exc_info=True)

    async def _calculate_engagement_loop(self):
        """
        Background loop that calculates engagement scores periodically.
        Stores results in TimescaleDB.
        """
        logger.info(f"🔄 Starting engagement calculation loop (every {self.calculation_interval}s)")

        try:
            while self.running:
                await asyncio.sleep(self.calculation_interval)

                if not self.running:
                    break

                # Calculate engagement for all active sessions
                active_sessions = list(self.tracker.sessions.keys())
                logger.debug(f"Calculating engagement for {len(active_sessions)} sessions")

                for session_id in active_sessions:
                    try:
                        await self._calculate_and_store_engagement(session_id)
                        self.metrics.engagement_calculations += 1
                        self.metrics.record_success()
                    except Exception as e:
                        self.metrics.engagement_calculation_errors += 1
                        self.metrics.record_error("engagement_calculation", str(e))
                        logger.error(f"Error calculating engagement for {session_id}: {e}")

        except asyncio.CancelledError:
            logger.info("Engagement calculation loop cancelled")
        except Exception as e:
            logger.error(f"Engagement calculation loop error: {e}", exc_info=True)

    async def _calculate_and_store_engagement(self, session_id: str):
        """
        Calculate engagement score for a session and store in database.

        Args:
            session_id: Session identifier
        """
        # Get session signals
        signals_dict = self.tracker.get_session_signals(session_id)
        if not signals_dict:
            return

        session = self.tracker.sessions.get(session_id)
        if not session:
            return

        # Create EngagementSignals object
        signals = EngagementSignals(
            chat_msgs_per_min=signals_dict["chat_msgs_per_min"],
            poll_participation=signals_dict["poll_participation"],
            active_users=signals_dict["active_users"],
            total_users=signals_dict["total_users"],
            reactions_per_min=signals_dict["reactions_per_min"],
            user_leave_rate=signals_dict["user_leave_rate"],
        )

        # Calculate engagement score
        score = self.calculator.calculate(signals)

        # Store in database
        try:
            async with AsyncSessionLocal() as db:
                metric = EngagementMetric(
                    time=datetime.now(timezone.utc),
                    session_id=session_id,
                    event_id=session.event_id,
                    engagement_score=score,
                    chat_msgs_per_min=signals.chat_msgs_per_min,
                    poll_participation=signals.poll_participation,
                    active_users=signals.active_users,
                    reactions_per_min=signals.reactions_per_min,
                    user_leave_rate=signals.user_leave_rate,
                    metadata={
                        "total_users": signals.total_users,
                        "category": self.calculator.categorize_engagement(score),
                    }
                )

                db.add(metric)
                await db.commit()

                logger.debug(
                    f"✅ Engagement stored: {session_id[:8]}... = {score:.2f} "
                    f"({self.calculator.categorize_engagement(score)})"
                )

                # Publish to Redis for real-time dashboard
                await self._publish_engagement_update(session_id, session.event_id, score, signals_dict)

                # Check for anomalies
                await self._detect_and_publish_anomaly(session_id, session.event_id, score, signals_dict)

        except Exception as e:
            logger.error(f"Failed to store engagement metric: {e}", exc_info=True)

    async def _publish_engagement_update(
        self,
        session_id: str,
        event_id: str,
        score: float,
        signals: dict
    ):
        """
        Publish engagement update to Redis for frontend consumption.

        Args:
            session_id: Session identifier
            event_id: Event identifier
            score: Engagement score
            signals: Raw signals dictionary
        """
        try:
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sessionId": session_id,
                "eventId": event_id,
                "score": score,
                "signals": signals,
            }

            # Publish to a dedicated channel for engagement updates
            await self.redis.publish(
                "engagement:update",
                json.dumps(payload)
            )

        except Exception as e:
            logger.error(f"Failed to publish engagement update: {e}")

    async def _detect_and_publish_anomaly(
        self,
        session_id: str,
        event_id: str,
        score: float,
        signals: dict
    ):
        """
        Detect anomalies and publish to Redis.

        Args:
            session_id: Session identifier
            event_id: Event identifier
            score: Engagement score
            signals: Raw signals dictionary
        """
        try:
            # Run anomaly detection
            anomaly_event = anomaly_detector.detect(
                session_id=session_id,
                event_id=event_id,
                engagement_score=score,
                signals=signals
            )

            if not anomaly_event:
                return

            # Store anomaly in database
            async with AsyncSessionLocal() as db:
                anomaly_record = Anomaly(
                    session_id=session_id,
                    event_id=event_id,
                    timestamp=anomaly_event.timestamp,
                    anomaly_type=anomaly_event.anomaly_type,
                    severity=anomaly_event.severity,
                    anomaly_score=anomaly_event.anomaly_score,
                    current_engagement=anomaly_event.current_engagement,
                    expected_engagement=anomaly_event.expected_engagement,
                    deviation=anomaly_event.deviation,
                    signals=anomaly_event.signals,
                    metadata=anomaly_event.metadata
                )

                db.add(anomaly_record)
                await db.commit()

                logger.info(
                    f"💾 Anomaly stored: {session_id[:8]}... - {anomaly_event.anomaly_type} ({anomaly_event.severity})"
                )

            # Publish anomaly to Redis for frontend
            await self._publish_anomaly_event(anomaly_event)

            # Trigger intervention based on anomaly
            await self._trigger_intervention(anomaly_event, signals)

        except Exception as e:
            logger.error(f"Failed to detect/store anomaly: {e}", exc_info=True)

    async def _publish_anomaly_event(self, anomaly_event):
        """
        Publish anomaly event to Redis for frontend consumption.

        Args:
            anomaly_event: AnomalyEvent object
        """
        try:
            payload = {
                "sessionId": anomaly_event.session_id,
                "eventId": anomaly_event.event_id,
                "timestamp": anomaly_event.timestamp.isoformat(),
                "type": anomaly_event.anomaly_type,
                "severity": anomaly_event.severity,
                "anomalyScore": anomaly_event.anomaly_score,
                "currentEngagement": anomaly_event.current_engagement,
                "expectedEngagement": anomaly_event.expected_engagement,
                "deviation": anomaly_event.deviation,
                "signals": anomaly_event.signals,
            }

            # Publish to anomaly channel
            await self.redis.publish(
                "anomaly:detected",
                json.dumps(payload)
            )

            logger.info(
                f"📢 Anomaly published: {anomaly_event.session_id[:8]}... - {anomaly_event.anomaly_type}"
            )

        except Exception as e:
            logger.error(f"Failed to publish anomaly event: {e}")

    async def _trigger_intervention(self, anomaly_event, signals):
        """
        Trigger Phase 5 Agent Orchestrator based on detected anomaly.

        RELIABILITY: Rate limited to prevent overwhelming users with interventions:
        - Max 1 intervention per 30 seconds per session
        - Max 10 interventions per 5 minutes per session
        - Max 100 interventions per hour per event

        The agent will:
        1. Perceive the anomaly
        2. Decide on intervention using Thompson Sampling
        3. Act (execute or wait for approval based on mode)
        4. Learn from the outcome

        Args:
            anomaly_event: Detected anomaly
            signals: Current engagement signals
        """
        try:
            # Rate limiting check
            rate_limiter = get_intervention_rate_limiter()
            is_allowed, rejection_reason = await rate_limiter.is_intervention_allowed(
                session_id=anomaly_event.session_id,
                event_id=anomaly_event.event_id
            )

            if not is_allowed:
                logger.info(
                    f"⏳ Intervention rate limited for session {anomaly_event.session_id[:8]}...: "
                    f"{rejection_reason}"
                )
                return
            # Get session context
            session_state = self.tracker.get_session_state(anomaly_event.session_id)
            session_context = {
                'session_id': anomaly_event.session_id,
                'event_id': anomaly_event.event_id,
                'duration': (datetime.now(timezone.utc) - session_state.last_activity).total_seconds() if session_state else 0,
                'connected_users': len(session_state.connected_users) if session_state else 0,
                'signals': signals
            }

            # Convert anomaly_event to Anomaly model for agent
            anomaly = Anomaly(
                session_id=anomaly_event.session_id,
                event_id=anomaly_event.event_id,
                anomaly_type=anomaly_event.anomaly_type,
                severity=anomaly_event.severity,
                detected_at=anomaly_event.timestamp,
                current_value=anomaly_event.current_engagement,
                baseline_value=anomaly_event.expected_engagement,
                deviation=anomaly_event.deviation,
                confidence=0.95,  # Anomaly detection confidence
                context=signals
            )

            # Auto-register session if not already registered (PRODUCTION-READY)
            if anomaly_event.session_id not in agent_manager.configs:
                # Get event agent settings from database (default to SEMI_AUTO)
                event_agent_mode = await self._get_event_agent_mode(anomaly_event.event_id)

                logger.info(
                    f"📝 Auto-registering session {anomaly_event.session_id[:8]}... "
                    f"with mode {event_agent_mode}"
                )

                agent_manager.register_session(
                    session_id=anomaly_event.session_id,
                    event_id=anomaly_event.event_id,
                    agent_mode=event_agent_mode
                )

            logger.info(
                f"🤖 Triggering Agent Orchestrator for {anomaly_event.session_id[:8]}... "
                f"({anomaly_event.anomaly_type} - {anomaly_event.severity})"
            )

            # Trigger the agent orchestrator (Phase 5)
            final_state = await agent_manager.run_agent(
                session_id=anomaly_event.session_id,
                engagement_score=anomaly_event.current_engagement,
                active_users=signals.get('active_users', 0),
                signals=signals,
                anomaly=anomaly,
                session_context=session_context
            )

            if final_state:
                logger.info(
                    f"✅ Agent completed: {anomaly_event.session_id[:8]}... - "
                    f"Intervention: {final_state.get('selected_intervention')} "
                    f"(confidence: {final_state.get('confidence', 0):.2f}, "
                    f"status: {final_state.get('status')})"
                )
            else:
                logger.warning(
                    f"⚠️ Agent did not run for {anomaly_event.session_id[:8]}... "
                    f"(session may not be registered or agent disabled)"
                )

        except Exception as e:
            logger.error(f"Failed to trigger agent orchestrator: {e}", exc_info=True)

            # Fallback to Phase 3 intervention selector if agent fails
            logger.info(f"Falling back to Phase 3 intervention selector")
            try:
                session_state = self.tracker.get_session_state(anomaly_event.session_id)
                session_context = {
                    'session_id': anomaly_event.session_id,
                    'event_id': anomaly_event.event_id,
                    'duration': (datetime.now(timezone.utc) - session_state.last_activity).total_seconds() if session_state else 0,
                    'connected_users': len(session_state.connected_users) if session_state else 0,
                    'signals': signals
                }

                recommendation = intervention_selector.select_intervention(
                    anomaly=anomaly_event,
                    session_context=session_context
                )

                if recommendation:
                    logger.info(
                        f"🎯 Fallback intervention: {recommendation.intervention_type} "
                        f"(confidence: {recommendation.confidence:.2f})"
                    )
                    async with AsyncSessionLocal() as db:
                        result = await self.intervention_executor.execute(
                            recommendation=recommendation,
                            db_session=db,
                            session_context=session_context
                        )
                        if result['success']:
                            intervention_selector.record_intervention(
                                session_id=anomaly_event.session_id,
                                intervention_type=recommendation.intervention_type
                            )
                            logger.info(
                                f"✅ Fallback intervention executed: {recommendation.intervention_type}"
                            )
            except Exception as fallback_error:
                logger.error(f"Fallback intervention also failed: {fallback_error}")

    async def _get_event_agent_mode(self, event_id: str):
        """
        Get agent mode setting for an event from database.

        PRODUCTION-READY: Returns SEMI_AUTO by default for best balance:
        - High confidence (>75%) interventions auto-execute
        - Low confidence (<75%) wait for organizer approval (if available)
        - Works automatically without organizer being online

        Args:
            event_id: Event identifier

        Returns:
            AgentMode enum (default: SEMI_AUTO)
        """
        try:
            from app.agents.engagement_conductor import AgentMode
            from app.models.event_agent_settings import EventAgentSettings
            from sqlalchemy import select

            async with AsyncSessionLocal() as db:
                # Use SQLAlchemy ORM to fetch event settings
                stmt = select(EventAgentSettings).where(
                    EventAgentSettings.event_id == event_id
                )
                result = await db.execute(stmt)
                settings = result.scalar_one_or_none()

                if settings and settings.agent_enabled:
                    mode_str = settings.agent_mode or 'SEMI_AUTO'
                    return AgentMode(mode_str)

                # Default to SEMI_AUTO for production
                # This provides the best balance of automation and safety
                return AgentMode.SEMI_AUTO

        except Exception as e:
            logger.warning(
                f"Could not fetch event agent settings for {event_id}: {e}. "
                f"Defaulting to SEMI_AUTO mode."
            )
            from app.agents.engagement_conductor import AgentMode
            return AgentMode.SEMI_AUTO

    async def _cleanup_loop(self):
        """Background loop that cleans up inactive sessions"""
        logger.info("🧹 Starting cleanup loop (every 5 minutes)")

        try:
            while self.running:
                await asyncio.sleep(300)  # 5 minutes

                if not self.running:
                    break

                cleaned = self.tracker.cleanup_inactive_sessions()
                if cleaned > 0:
                    logger.info(f"🧹 Cleaned up {cleaned} inactive sessions")

        except asyncio.CancelledError:
            logger.info("Cleanup loop cancelled")
        except Exception as e:
            logger.error(f"Cleanup loop error: {e}", exc_info=True)
