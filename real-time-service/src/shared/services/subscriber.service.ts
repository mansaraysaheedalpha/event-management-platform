import { Inject, Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { EventEmitter2 } from '@nestjs/event-emitter';
import { Redis } from 'ioredis';
import { REDIS_SUBSCRIBER_CLIENT } from '../redis.constants';
import { getErrorMessage } from 'src/common/utils/error.utils';

/**
 * SubscriberService listens to multiple Redis Pub/Sub channels and emits
 * corresponding events within the NestJS event system.
 */
@Injectable()
export class SubscriberService implements OnModuleInit {
  private readonly logger = new Logger(SubscriberService.name);

  constructor(
    @Inject(REDIS_SUBSCRIBER_CLIENT) private readonly subscriber: Redis,
    private readonly eventEmitter: EventEmitter2,
  ) {}

  /**
   * Lifecycle hook that sets up Redis subscriptions.
   */
  async onModuleInit() {
    this.logger.log('Initializing Redis message subscriber...');

    this.subscriber.on('message', (channel, message) => {
      this.handleIncomingMessage(channel, message);
    });

    try {
      await this.subscriber.subscribe(
        'agenda-updates',
        'audit-events',
        'security-events',
        'monetization-events',
        'system-health-events',
        'platform.analytics.check-in.v1',
        'sync-events',
        'ai-suggestions',
        'heatmap-events',
        'sales-events',
        'proximity-updates',
        'oracle.predictions.sentiment.v1',
        'capacity-events',
        'notification-events',
        'system-metrics-events',
      );
      this.logger.log('Successfully subscribed to all Redis Pub/Sub channels.');
    } catch (err) {
      this.logger.error('Failed to subscribe to Redis channels', err);
    }
  }

  /**
   * Handles incoming messages from Redis and emits them internally.
   */
  private handleIncomingMessage(channel: string, message: string) {
    try {
      this.logger.log(`Received message from Redis on channel '${channel}'`);
      const unknownPayload: unknown = JSON.parse(message);
      this.eventEmitter.emit(channel, unknownPayload);
    } catch (error) {
      this.logger.error(
        `Failed to process incoming message from channel '${channel}': ${getErrorMessage(error)}`,
        message,
      );
    }
  }
}
