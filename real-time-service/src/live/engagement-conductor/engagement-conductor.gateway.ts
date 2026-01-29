// src/live/engagement-conductor/engagement-conductor.gateway.ts
import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  OnGatewayInit,
  OnGatewayConnection,
  OnGatewayDisconnect,
  ConnectedSocket,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger, Inject, OnModuleInit, OnModuleDestroy } from '@nestjs/common';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { PrismaService } from 'src/prisma.service';

/**
 * Get allowed CORS origins from environment
 * SECURITY: Never allow all origins in production
 */
function getAllowedOrigins(): string[] | boolean {
  const origins = process.env.CORS_ORIGINS;

  // In development, allow localhost variants
  if (process.env.NODE_ENV === 'development') {
    return [
      'http://localhost:3000',
      'http://localhost:3001',
      'http://127.0.0.1:3000',
      'http://127.0.0.1:3001',
    ];
  }

  // In production, require explicit configuration
  if (!origins) {
    console.warn(
      'SECURITY WARNING: CORS_ORIGINS not configured. ' +
      'WebSocket connections will be rejected from all origins.'
    );
    return false; // Reject all if not configured
  }

  // Parse comma-separated origins
  return origins.split(',').map(origin => origin.trim()).filter(Boolean);
}

/**
 * Engagement Conductor Gateway
 *
 * Forwards agent state events from the agent service to WebSocket clients.
 *
 * SECURITY: CORS is restricted to explicitly configured origins only.
 *
 * Events forwarded:
 * - agent.status: Agent status changes (MONITORING, WAITING_APPROVAL, INTERVENING, etc.)
 * - agent.decision: Agent makes a decision about intervention
 * - agent.intervention.executed: Intervention is executed
 */
@WebSocketGateway({
  cors: {
    origin: getAllowedOrigins(),
    credentials: true,
    methods: ['GET', 'POST'],
  },
  namespace: '/events',
})
export class EngagementConductorGateway
  implements OnGatewayInit, OnGatewayConnection, OnGatewayDisconnect, OnModuleInit, OnModuleDestroy
{
  @WebSocketServer()
  server: Server;

  private readonly logger = new Logger('EngagementConductorGateway');
  private redisSubscriber: Redis;
  private subscribedChannels = new Set<string>();
  // Track how many clients are subscribed to each channel for cleanup
  private channelSubscriberCount = new Map<string, number>();

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly prisma: PrismaService,
  ) {}

  async onModuleInit() {
    // Create a separate Redis client for pub/sub
    // (can't use the same client for both pub/sub and regular commands)
    this.redisSubscriber = this.redis.duplicate();

    this.redisSubscriber.on('message', (channel: string, message: string) => {
      try {
        const event = JSON.parse(message);
        this.handleAgentEvent(event);
      } catch (error) {
        this.logger.error(`Failed to parse Redis message: ${error}`);
      }
    });

    this.logger.log('EngagementConductorGateway initialized');
  }

  async onModuleDestroy() {
    if (this.redisSubscriber) {
      await this.redisSubscriber.quit();
    }
  }

  afterInit(server: Server) {
    this.logger.log('EngagementConductorGateway WebSocket initialized');
  }

  async handleConnection(@ConnectedSocket() client: AuthenticatedSocket) {
    const user = getAuthenticatedUser(client);
    if (!user) {
      this.logger.warn(`Unauthenticated client ${client.id} attempted to connect`);
      client.disconnect();
      return;
    }

    this.logger.log(`Client ${client.id} connected (user: ${user.sub})`);
  }

  async handleDisconnect(@ConnectedSocket() client: AuthenticatedSocket) {
    const user = getAuthenticatedUser(client);
    if (user) {
      this.logger.log(`Client ${client.id} disconnected (user: ${user.sub})`);
    }
  }

  /**
   * Validates if a user has access to a specific session.
   * Checks if the user is the organizer of the event associated with the session.
   *
   * @param userId - The user ID to validate
   * @param sessionId - The session ID to check access for
   * @returns Promise<boolean> - True if user has access, false otherwise
   */
  private async validateSessionAccess(
    userId: string,
    sessionId: string,
  ): Promise<boolean> {
    try {
      // Find the chat session and verify user has access
      const chatSession = await this.prisma.chatSession.findUnique({
        where: { id: sessionId },
        select: {
          id: true,
          organizationId: true,
          participants: true,
        },
      });

      if (!chatSession) {
        this.logger.warn(`Session ${sessionId} not found in database`);
        return false;
      }

      // Check if user is a participant in this session
      // Note: Event organizer authorization should be verified via event-lifecycle-service
      if (!chatSession.participants.includes(userId)) {
        this.logger.warn(
          `User ${userId} attempted to access session ${sessionId} without authorization`,
        );
        return false;
      }

      return true;
    } catch (error) {
      this.logger.error(
        `Error validating session access for user ${userId}, session ${sessionId}: ${error}`,
      );
      return false;
    }
  }

  /**
   * Subscribe to agent events for a specific session
   */
  @SubscribeMessage('agent:subscribe')
  async handleSubscribeToAgentEvents(
    @ConnectedSocket() client: AuthenticatedSocket,
    payload: { sessionId: string },
  ) {
    const user = getAuthenticatedUser(client);
    if (!user) {
      return { success: false, error: 'Unauthorized' };
    }

    const { sessionId } = payload;

    // Verify user has access to this session
    const hasAccess = await this.validateSessionAccess(user.sub, sessionId);
    if (!hasAccess) {
      this.logger.warn(
        `Client ${client.id} (user: ${user.sub}) denied access to session ${sessionId}`,
      );
      return { success: false, error: 'Forbidden: You do not have access to this session' };
    }

    // Join socket room for this session
    await client.join(`session:${sessionId}:agent`);

    // Subscribe to Redis channel if not already subscribed
    const channel = `session:${sessionId}:events`;
    if (!this.subscribedChannels.has(channel)) {
      await this.redisSubscriber.subscribe(channel);
      this.subscribedChannels.add(channel);
      this.channelSubscriberCount.set(channel, 0);
      this.logger.log(`Subscribed to Redis channel: ${channel}`);
    }

    // Increment subscriber count
    const count = this.channelSubscriberCount.get(channel) || 0;
    this.channelSubscriberCount.set(channel, count + 1);

    this.logger.log(
      `Client ${client.id} subscribed to agent events for session ${sessionId} (${count + 1} subscribers)`,
    );

    return { success: true, sessionId };
  }

  /**
   * Unsubscribe from agent events for a specific session
   */
  @SubscribeMessage('agent:unsubscribe')
  async handleUnsubscribeFromAgentEvents(
    @ConnectedSocket() client: AuthenticatedSocket,
    payload: { sessionId: string },
  ) {
    const user = getAuthenticatedUser(client);
    if (!user) {
      return { success: false, error: 'Unauthorized' };
    }

    const { sessionId } = payload;

    // Leave socket room
    await client.leave(`session:${sessionId}:agent`);

    // Decrement subscriber count and unsubscribe if no more subscribers
    const channel = `session:${sessionId}:events`;
    await this.cleanupChannelIfEmpty(channel);

    this.logger.log(
      `Client ${client.id} unsubscribed from agent events for session ${sessionId}`,
    );

    return { success: true, sessionId };
  }

  /**
   * Clean up Redis channel subscription if no more clients are subscribed
   */
  private async cleanupChannelIfEmpty(channel: string) {
    const count = this.channelSubscriberCount.get(channel) || 0;
    if (count > 0) {
      this.channelSubscriberCount.set(channel, count - 1);
    }

    if (count <= 1 && this.subscribedChannels.has(channel)) {
      try {
        await this.redisSubscriber.unsubscribe(channel);
        this.subscribedChannels.delete(channel);
        this.channelSubscriberCount.delete(channel);
        this.logger.log(`Unsubscribed from Redis channel: ${channel} (no more subscribers)`);
      } catch (error) {
        this.logger.error(`Failed to unsubscribe from Redis channel ${channel}: ${error}`);
      }
    }
  }

  /**
   * Handle agent event from Redis and forward to WebSocket clients
   */
  private handleAgentEvent(event: any) {
    const { type, session_id, data } = event;

    if (!session_id) {
      this.logger.warn(`Received agent event without session_id: ${type}`);
      return;
    }

    // Emit to all clients subscribed to this session's agent events
    const room = `session:${session_id}:agent`;
    this.server.to(room).emit(type, data);

    this.logger.debug(`Forwarded ${type} event to room ${room}`);
  }
}
