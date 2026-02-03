// src/live/engagement-conductor/engagement-stream.listener.ts
import { Injectable, Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { Server } from 'socket.io';
import { WebSocketServer } from '@nestjs/websockets';

/**
 * Engagement Stream Listener
 *
 * Listens to engagement and anomaly events from Redis (via SubscriberService)
 * and forwards them to WebSocket clients subscribed to the engagement dashboard.
 *
 * Events handled:
 * - engagement:update: Real-time engagement scores and signals (chat_msgs_per_min, active_users, etc.)
 * - anomaly:detected: Anomaly detection events (engagement drops, spikes, etc.)
 *
 * These events originate from the agent-service and are published to Redis Pub/Sub.
 * The SubscriberService receives them and emits them as NestJS events.
 * This listener forwards them to the appropriate WebSocket rooms.
 */
@Injectable()
export class EngagementStreamListener {
  private readonly logger = new Logger(EngagementStreamListener.name);
  private server: Server | null = null;

  /**
   * Set the WebSocket server instance (injected from gateway)
   */
  setServer(server: Server) {
    this.server = server;
    this.logger.log('WebSocket server registered for engagement stream forwarding');
  }

  /**
   * Handle engagement:update events from Redis
   *
   * Payload structure from agent-service:
   * {
   *   timestamp: string (ISO),
   *   sessionId: string,
   *   eventId: string,
   *   score: number (0-1),
   *   signals: {
   *     chat_msgs_per_min: number,
   *     poll_participation: number,
   *     active_users: number,
   *     total_users: number,
   *     reactions_per_min: number,
   *     user_leave_rate: number
   *   }
   * }
   */
  @OnEvent('engagement:update')
  handleEngagementUpdate(payload: unknown) {
    if (!this.isValidEngagementPayload(payload)) {
      this.logger.warn('Invalid engagement:update payload received', payload);
      return;
    }

    const { sessionId } = payload;

    if (!this.server) {
      this.logger.warn('WebSocket server not available, cannot forward engagement:update');
      return;
    }

    // Forward to clients subscribed to this session's agent events
    const room = `session:${sessionId}:agent`;
    this.server.to(room).emit('engagement:update', payload);

    this.logger.debug(
      `Forwarded engagement:update to room ${room} (score: ${payload.score?.toFixed(2)})`,
    );
  }

  /**
   * Handle anomaly:detected events from Redis
   *
   * Payload structure from agent-service:
   * {
   *   sessionId: string,
   *   eventId: string,
   *   timestamp: string (ISO),
   *   type: string (ENGAGEMENT_DROP, PARTICIPATION_DECLINE, etc.),
   *   severity: string (WARNING, CRITICAL),
   *   anomalyScore: number,
   *   currentEngagement: number,
   *   expectedEngagement: number,
   *   deviation: number,
   *   signals: object
   * }
   */
  @OnEvent('anomaly:detected')
  handleAnomalyDetected(payload: unknown) {
    if (!this.isValidAnomalyPayload(payload)) {
      this.logger.warn('Invalid anomaly:detected payload received', payload);
      return;
    }

    const { sessionId, type, severity } = payload;

    if (!this.server) {
      this.logger.warn('WebSocket server not available, cannot forward anomaly:detected');
      return;
    }

    // Forward to clients subscribed to this session's agent events
    const room = `session:${sessionId}:agent`;
    this.server.to(room).emit('anomaly:detected', payload);

    this.logger.log(
      `Forwarded anomaly:detected to room ${room} (type: ${type}, severity: ${severity})`,
    );
  }

  /**
   * Type guard for valid engagement payload
   */
  private isValidEngagementPayload(
    payload: unknown,
  ): payload is EngagementUpdatePayload {
    if (typeof payload !== 'object' || payload === null) {
      return false;
    }

    const p = payload as Record<string, unknown>;
    return (
      typeof p.sessionId === 'string' &&
      typeof p.score === 'number' &&
      typeof p.signals === 'object' &&
      p.signals !== null
    );
  }

  /**
   * Type guard for valid anomaly payload
   */
  private isValidAnomalyPayload(
    payload: unknown,
  ): payload is AnomalyDetectedPayload {
    if (typeof payload !== 'object' || payload === null) {
      return false;
    }

    const p = payload as Record<string, unknown>;
    return (
      typeof p.sessionId === 'string' &&
      typeof p.type === 'string' &&
      typeof p.severity === 'string'
    );
  }
}

// Type definitions for payloads
interface EngagementSignals {
  chat_msgs_per_min: number;
  poll_participation: number;
  active_users: number;
  total_users: number;
  reactions_per_min: number;
  user_leave_rate: number;
}

interface EngagementUpdatePayload {
  timestamp: string;
  sessionId: string;
  eventId: string;
  score: number;
  signals: EngagementSignals;
}

interface AnomalyDetectedPayload {
  sessionId: string;
  eventId: string;
  timestamp: string;
  type: string;
  severity: string;
  anomalyScore: number;
  currentEngagement: number;
  expectedEngagement: number;
  deviation: number;
  signals: Record<string, unknown>;
}
