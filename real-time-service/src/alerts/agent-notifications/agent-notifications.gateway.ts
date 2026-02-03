import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  ConnectedSocket,
  MessageBody,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Inject, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import Redis from 'ioredis';
import { REDIS_SUBSCRIBER_CLIENT } from '../../shared/redis.constants';
import { AgentNotificationsService } from './agent-notifications.service';
import {
  AuthenticatedSocket,
  getAuthenticatedUser,
} from '../../common/utils/auth.utils';
import { AgentNotificationPayload } from './dto/agent-notification.dto';

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class AgentNotificationsGateway implements OnModuleInit, OnModuleDestroy {
  @WebSocketServer() server: Server;

  private readonly logger = new Logger(AgentNotificationsGateway.name);
  private redisSubscriber: Redis;
  private subscribedChannels = new Set<string>();
  private channelSubscriberCount = new Map<string, number>();

  constructor(
    @Inject(REDIS_SUBSCRIBER_CLIENT) private readonly redisClient: Redis,
    private readonly notificationsService: AgentNotificationsService,
  ) {}

  async onModuleInit() {
    this.redisSubscriber = this.redisClient.duplicate();

    this.redisSubscriber.on('message', (channel: string, message: string) => {
      this.handleRedisMessage(channel, message);
    });

    this.redisSubscriber.on('error', (error) => {
      this.logger.error('Redis subscriber error:', error);
    });

    this.redisSubscriber.on('connect', () => {
      this.logger.log('Redis subscriber connected for agent notifications');
    });
  }

  async onModuleDestroy() {
    for (const channel of this.subscribedChannels) {
      await this.redisSubscriber.unsubscribe(channel);
    }
    await this.redisSubscriber.quit();
  }

  @SubscribeMessage('agent-notifications.subscribe')
  async handleSubscribe(
    @ConnectedSocket() client: AuthenticatedSocket,
    @MessageBody() payload: { eventId: string },
  ) {
    const user = getAuthenticatedUser(client);
    if (!user?.permissions?.includes('dashboard:read:live')) {
      return { success: false, error: 'Forbidden' };
    }

    const { eventId } = payload;
    const room = `agent-notifications:${eventId}`;
    const channel = `agent:notifications:${eventId}`;

    await client.join(room);

    // Subscribe to Redis channel if not already
    const count = this.channelSubscriberCount.get(channel) || 0;
    if (count === 0) {
      await this.redisSubscriber.subscribe(channel);
      this.subscribedChannels.add(channel);
      this.logger.log(`Subscribed to Redis channel: ${channel}`);
    }
    this.channelSubscriberCount.set(channel, count + 1);

    // Send initial unread count
    const unreadCount = await this.notificationsService.getUnreadCount(
      eventId,
      user.sub,
    );

    this.logger.log(
      `User ${user.sub} subscribed to agent notifications for event ${eventId}`,
    );

    return { success: true, unreadCount };
  }

  @SubscribeMessage('agent-notifications.unsubscribe')
  async handleUnsubscribe(
    @ConnectedSocket() client: AuthenticatedSocket,
    @MessageBody() payload: { eventId: string },
  ) {
    const { eventId } = payload;
    const room = `agent-notifications:${eventId}`;
    const channel = `agent:notifications:${eventId}`;

    await client.leave(room);

    // Unsubscribe from Redis if no more listeners
    const count = (this.channelSubscriberCount.get(channel) || 1) - 1;
    if (count <= 0) {
      await this.redisSubscriber.unsubscribe(channel);
      this.subscribedChannels.delete(channel);
      this.channelSubscriberCount.delete(channel);
      this.logger.log(`Unsubscribed from Redis channel: ${channel}`);
    } else {
      this.channelSubscriberCount.set(channel, count);
    }

    return { success: true };
  }

  private async handleRedisMessage(channel: string, message: string) {
    // Only process agent notification channels
    if (!channel.startsWith('agent:notifications:')) {
      return;
    }

    try {
      const payload: AgentNotificationPayload = JSON.parse(message);
      const eventId = payload.event_id;

      // Persist to database
      const notification =
        await this.notificationsService.createNotification(payload);

      // Broadcast to connected organizers
      const room = `agent-notifications:${eventId}`;
      this.server.to(room).emit('agent-notification.new', {
        id: notification.id,
        type: notification.type,
        severity: notification.severity,
        sessionId: notification.sessionId,
        data: notification.data,
        createdAt: notification.createdAt.toISOString(),
      });

      this.logger.log(
        `Broadcasted agent notification ${notification.id} to room ${room}`,
      );
    } catch (error) {
      this.logger.error(
        `Error processing Redis message from ${channel}:`,
        error,
      );
    }
  }
}
