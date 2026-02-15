// src/live/engagement-conductor/engagement-conductor.gateway.ts
import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  MessageBody,
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
import { WEBSOCKET_CORS_CONFIG } from 'src/common/config/cors.config';
import { EngagementStreamListener } from './engagement-stream.listener';

/**
 * Engagement Conductor Gateway
 *
 * Forwards agent state events from the agent service to WebSocket clients.
 *
 * SECURITY: CORS is restricted to explicitly configured origins only.
 * Uses shared CORS config for consistency across all gateways.
 *
 * Events forwarded:
 * - agent.status: Agent status changes (MONITORING, WAITING_APPROVAL, INTERVENING, etc.)
 * - agent.decision: Agent makes a decision about intervention
 * - agent.intervention.executed: Intervention is executed
 */
@WebSocketGateway({
  cors: {
    ...WEBSOCKET_CORS_CONFIG,
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

  // Track Redis connection state
  private redisConnected = false;
  private reconnectAttempts = 0;
  private readonly maxReconnectAttempts = 10;

  // MED-8 FIX: Rate limiting for subscribe events
  private subscribeRateLimit = new Map<string, number>();
  private readonly SUBSCRIBE_RATE_LIMIT_MS = 2000; // 2 seconds between subscribes

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly prisma: PrismaService,
    private readonly engagementStreamListener: EngagementStreamListener,
  ) {}

  async onModuleInit() {
    // Create a separate Redis client for pub/sub
    // (can't use the same client for both pub/sub and regular commands)
    this.redisSubscriber = this.redis.duplicate();

    // Set up Redis connection event handlers
    this.setupRedisEventHandlers();

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

  /**
   * Set up Redis connection event handlers for robust reconnection handling
   */
  private setupRedisEventHandlers() {
    // Handle successful connection
    this.redisSubscriber.on('connect', () => {
      this.redisConnected = true;
      this.reconnectAttempts = 0;
      this.logger.log('Redis subscriber connected');
    });

    // Handle ready state (after authentication if needed)
    this.redisSubscriber.on('ready', async () => {
      this.logger.log('Redis subscriber ready');
      // Resubscribe to all channels after reconnection
      await this.resubscribeToAllChannels();
    });

    // Handle connection errors
    this.redisSubscriber.on('error', (error) => {
      this.logger.error(`Redis subscriber error: ${error.message}`);
      // Don't mark as disconnected here - let 'close' event handle that
    });

    // Handle connection close
    this.redisSubscriber.on('close', () => {
      this.redisConnected = false;
      this.logger.warn('Redis subscriber connection closed');
    });

    // Handle reconnection attempts
    this.redisSubscriber.on('reconnecting', (delay: number) => {
      this.reconnectAttempts++;
      this.logger.log(
        `Redis subscriber reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`,
      );

      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        this.logger.error(
          `Redis subscriber failed to reconnect after ${this.maxReconnectAttempts} attempts. ` +
          `Agent events will not be forwarded until connection is restored.`,
        );
      }
    });

    // Handle end (when reconnection is given up)
    this.redisSubscriber.on('end', () => {
      this.redisConnected = false;
      this.logger.error('Redis subscriber connection ended - no more reconnection attempts');
    });
  }

  /**
   * Resubscribe to all channels after Redis reconnection
   * This ensures we don't lose subscriptions during connection interruptions
   */
  private async resubscribeToAllChannels() {
    if (this.subscribedChannels.size === 0) {
      return;
    }

    this.logger.log(`Resubscribing to ${this.subscribedChannels.size} channels after reconnection`);

    const channels = Array.from(this.subscribedChannels);

    for (const channel of channels) {
      try {
        await this.redisSubscriber.subscribe(channel);
        this.logger.debug(`Resubscribed to channel: ${channel}`);
      } catch (error) {
        this.logger.error(`Failed to resubscribe to channel ${channel}: ${error}`);
        // Remove from tracked channels if resubscription fails
        this.subscribedChannels.delete(channel);
        this.channelSubscriberCount.delete(channel);
      }
    }

    this.logger.log(`Successfully resubscribed to ${this.subscribedChannels.size} channels`);
  }

  /**
   * Check if Redis is currently connected
   */
  isRedisConnected(): boolean {
    return this.redisConnected;
  }

  async onModuleDestroy() {
    if (this.redisSubscriber) {
      await this.redisSubscriber.quit();
    }
  }

  afterInit(server: Server) {
    // Pass server to engagement stream listener for event forwarding
    this.engagementStreamListener.setServer(server);
    this.logger.log('EngagementConductorGateway WebSocket initialized');
  }

  async handleConnection(@ConnectedSocket() client: AuthenticatedSocket) {
    try {
      const user = getAuthenticatedUser(client);
      this.logger.log(`Client ${client.id} connected (user: ${user.sub})`);
    } catch {
      // getAuthenticatedUser throws UnauthorizedException for unauthenticated clients
      this.logger.warn(`Unauthenticated client ${client.id} attempted to connect`);
      client.disconnect();
    }
  }

  async handleDisconnect(@ConnectedSocket() client: AuthenticatedSocket) {
    try {
      const user = getAuthenticatedUser(client);
      this.logger.log(`Client ${client.id} disconnected (user: ${user.sub})`);
    } catch {
      // Unauthenticated client disconnected - no action needed
      this.logger.debug(`Unauthenticated client ${client.id} disconnected`);
    }

    // MED-9 FIX: Decrement subscriber counts for all rooms this client was in
    // to prevent leaked Redis subscriptions when clients disconnect without unsubscribing
    const rooms = Array.from(client.rooms || []);
    for (const room of rooms) {
      if (room.startsWith('session:') && room.endsWith(':agent')) {
        const sessionId = room.replace('session:', '').replace(':agent', '');
        const channel = `session:${sessionId}:events`;
        await this.cleanupChannelIfEmpty(channel);
      }
    }

    // MED-8: Clean up rate limit tracking for disconnected client
    this.subscribeRateLimit.delete(client.id);
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

      // CRIT-7 FIX: Check organization membership instead of chat participant list.
      // The engagement conductor dashboard is for event organizers, not chat participants.
      // Verify the user belongs to the organization that owns this session.
      const orgMember = await this.prisma.organizationMember.findFirst({
        where: {
          organizationId: chatSession.organizationId,
          userId: userId,
        },
      });

      if (!orgMember) {
        this.logger.warn(
          `User ${userId} is not an organization member for session ${sessionId}`,
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
   * Validate session ID format to prevent injection attacks
   */
  private isValidSessionId(sessionId: unknown): sessionId is string {
    if (typeof sessionId !== 'string') return false;
    if (sessionId.length === 0 || sessionId.length > 100) return false;
    // Allow alphanumeric, hyphens, and underscores (UUIDs and event_ format)
    return /^[a-zA-Z0-9_-]+$/.test(sessionId);
  }

  /**
   * Subscribe to agent events for a specific session
   */
  @SubscribeMessage('agent:subscribe')
  async handleSubscribeToAgentEvents(
    @ConnectedSocket() client: AuthenticatedSocket,
    @MessageBody() payload: { sessionId: string },
  ) {
    let user;
    try {
      user = getAuthenticatedUser(client);
    } catch {
      return { success: false, error: 'Unauthorized' };
    }

    // Handle undefined payload gracefully
    if (!payload || typeof payload !== 'object') {
      this.logger.warn(`Client ${client.id} sent invalid payload to agent:subscribe`);
      return { success: false, error: 'Invalid payload: sessionId is required' };
    }

    const { sessionId } = payload;

    // Validate sessionId format
    if (!this.isValidSessionId(sessionId)) {
      this.logger.warn(`Client ${client.id} sent invalid session ID format`);
      return { success: false, error: 'Invalid session ID format' };
    }

    // MED-8 FIX: Rate limit subscribe events per client
    const now = Date.now();
    const lastSubscribeTime = this.subscribeRateLimit.get(client.id);
    if (lastSubscribeTime && now - lastSubscribeTime < this.SUBSCRIBE_RATE_LIMIT_MS) {
      this.logger.warn(`Client ${client.id} rate limited on agent:subscribe`);
      return { success: false, error: 'Rate limited. Please wait before subscribing again.' };
    }
    this.subscribeRateLimit.set(client.id, now);

    // Check Redis connection status
    if (!this.redisConnected) {
      this.logger.warn(
        `Client ${client.id} attempted to subscribe but Redis is disconnected`,
      );
      return {
        success: false,
        error: 'Service temporarily unavailable - Redis connection lost. Please retry.',
      };
    }

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
      try {
        await this.redisSubscriber.subscribe(channel);
        this.subscribedChannels.add(channel);
        this.channelSubscriberCount.set(channel, 0);
        this.logger.log(`Subscribed to Redis channel: ${channel}`);
      } catch (error) {
        this.logger.error(`Failed to subscribe to Redis channel ${channel}: ${error}`);
        return {
          success: false,
          error: 'Failed to subscribe to agent events. Please retry.',
        };
      }
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
    @MessageBody() payload: { sessionId: string },
  ) {
    let user;
    try {
      user = getAuthenticatedUser(client);
    } catch {
      return { success: false, error: 'Unauthorized' };
    }

    // Handle undefined payload gracefully
    if (!payload || typeof payload !== 'object') {
      return { success: false, error: 'Invalid payload: sessionId is required' };
    }

    const { sessionId } = payload;

    // Validate sessionId format
    if (!this.isValidSessionId(sessionId)) {
      return { success: false, error: 'Invalid session ID format' };
    }

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
