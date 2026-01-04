"""
Engagement Signal Collector
Subscribes to platform events via Redis and calculates engagement scores
"""
import asyncio
import json
import logging
from typing import Optional
from datetime import datetime

from app.core.redis_client import RedisClient
from app.collectors.session_tracker import SessionTracker, session_tracker
from app.utils.engagement_score import EngagementScoreCalculator, EngagementSignals, engagement_calculator
from app.agents.anomaly_detector import AnomalyDetector, anomaly_detector
from app.db.timescale import AsyncSessionLocal
from app.db.models import EngagementMetric
from app.models.anomaly import Anomaly
from sqlalchemy import UUID

logger = logging.getLogger(__name__)


class EngagementSignalCollector:
    """
    Collects engagement signals from Redis Pub/Sub channels.
    Calculates engagement scores and stores them in TimescaleDB.
    """

    # Redis channels to subscribe to
    CHAT_CHANNEL = "platform.events.chat.message.v1"
    POLL_VOTE_CHANNEL = "platform.events.poll.vote.v1"
    POLL_CLOSED_CHANNEL = "platform.events.poll.closed.v1"
    SYNC_CHANNEL = "sync-events"

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
            redis_client: Redis client for Pub/Sub
            tracker: Session tracker (uses global if None)
            calculator: Engagement calculator (uses global if None)
            calculation_interval: Seconds between engagement calculations
        """
        self.redis = redis_client
        self.tracker = tracker or session_tracker
        self.calculator = calculator or engagement_calculator
        self.calculation_interval = calculation_interval
        self.running = False
        self.tasks = []

    async def start(self):
        """Start collecting signals and calculating engagement"""
        if self.running:
            logger.warning("Signal collector already running")
            return

        self.running = True
        logger.info("🚀 Starting Engagement Signal Collector...")

        # Subscribe to Redis channels
        pubsub = await self.redis.subscribe(
            self.CHAT_CHANNEL,
            self.POLL_VOTE_CHANNEL,
            self.POLL_CLOSED_CHANNEL,
            self.SYNC_CHANNEL,
        )

        logger.info(f"📡 Subscribed to {len([self.CHAT_CHANNEL, self.POLL_VOTE_CHANNEL, self.POLL_CLOSED_CHANNEL, self.SYNC_CHANNEL])} channels")

        # Start background tasks
        self.tasks = [
            asyncio.create_task(self._listen_to_events(pubsub)),
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

    async def _listen_to_events(self, pubsub):
        """
        Listen to Redis Pub/Sub events and process them.

        Args:
            pubsub: Redis pubsub object
        """
        logger.info("👂 Listening for platform events...")

        try:
            async for message in pubsub.listen():
                if not self.running:
                    break

                if message["type"] != "message":
                    continue

                channel = message["channel"]
                data = message["data"]

                try:
                    # Parse JSON data
                    event_data = json.loads(data) if isinstance(data, str) else data

                    # Route to appropriate handler
                    if channel == self.CHAT_CHANNEL:
                        await self._handle_chat_message(event_data)
                    elif channel == self.POLL_VOTE_CHANNEL:
                        await self._handle_poll_vote(event_data)
                    elif channel == self.POLL_CLOSED_CHANNEL:
                        await self._handle_poll_closed(event_data)
                    elif channel == self.SYNC_CHANNEL:
                        await self._handle_sync_event(event_data)

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse event data: {e}")
                except Exception as e:
                    logger.error(f"Error processing event: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("Event listener cancelled")
        except Exception as e:
            logger.error(f"Event listener error: {e}", exc_info=True)

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
        session_id = event_data.get("sessionId")
        event_id = event_data.get("eventId")

        if not session_id or not event_id:
            logger.warning(f"Missing session/event ID in chat message: {event_data}")
            return

        self.tracker.record_chat_message(session_id, event_id)
        logger.debug(f"📨 Chat message recorded for session {session_id}")

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
        session_id = event_data.get("sessionId")
        event_id = event_data.get("eventId")
        poll_id = event_data.get("pollId")

        if not session_id or not event_id or not poll_id:
            logger.warning(f"Missing data in poll vote: {event_data}")
            return

        self.tracker.record_poll_vote(session_id, event_id, poll_id)
        logger.debug(f"🗳️ Poll vote recorded for session {session_id}")

    async def _handle_poll_closed(self, event_data: dict):
        """Handle poll closed event"""
        # Could use this to reset poll tracking if needed
        logger.debug(f"Poll closed: {event_data.get('pollId')}")

    async def _handle_sync_event(self, event_data: dict):
        """
        Handle sync events (could include user presence, reactions, etc.)

        Expected data format varies based on event type
        """
        event_type = event_data.get("type")
        session_id = event_data.get("sessionId")
        event_id = event_data.get("eventId")

        if not session_id or not event_id:
            return

        # Handle different sync event types
        if event_type == "user_join":
            user_id = event_data.get("userId")
            if user_id:
                self.tracker.record_user_join(session_id, event_id, user_id)
                logger.debug(f"👋 User {user_id} joined session {session_id}")

        elif event_type == "user_leave":
            user_id = event_data.get("userId")
            if user_id:
                self.tracker.record_user_leave(session_id, event_id, user_id)
                logger.debug(f"👋 User {user_id} left session {session_id}")

        elif event_type == "reaction":
            self.tracker.record_reaction(session_id, event_id)
            logger.debug(f"❤️ Reaction recorded for session {session_id}")

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
                    except Exception as e:
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
                    time=datetime.utcnow(),
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
                "timestamp": datetime.utcnow().isoformat(),
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
