import { Inject, Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { EventEmitter2 } from '@nestjs/event-emitter';
import { Redis } from 'ioredis';
import { REDIS_SUBSCRIBER_CLIENT } from '../shared.module';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { AgendaUpdatePayload } from 'src/live/agenda/agenda.service';

// This is our "type guard" function.
// It checks if an unknown object matches the AgendaUpdatePayload interface.
function isAgendaUpdatePayload(
  payload: unknown,
): payload is AgendaUpdatePayload {
  const p = payload as AgendaUpdatePayload;
  return (
    typeof p === 'object' &&
    p !== null &&
    typeof p.eventId === 'string' &&
    typeof p.updateType === 'string' &&
    typeof p.sessionData === 'object'
  );
}

@Injectable()
export class SubscriberService implements OnModuleInit {
  private readonly logger = new Logger(SubscriberService.name);

  constructor(
    @Inject(REDIS_SUBSCRIBER_CLIENT) private readonly subscriber: Redis,
    private readonly eventEmitter: EventEmitter2,
  ) {}

  /**
   * This NestJS lifecycle hook runs once the module is initialized.
   */
  // FIX: Make the lifecycle hook async to allow for await.
  async onModuleInit() {
    this.logger.log('Initializing Redis message subscriber...');

    this.subscriber.on('message', (channel, message) => {
      this.handleIncomingMessage(channel, message);
    });

    try {
      // FIX: We now `await` the subscribe command.
      await this.subscriber.subscribe(
        'agenda-updates',
        'audit-events',
        'security-events',
        'monetization-events',
        'system-health-events',
        'platform.analytics.check-in.v1',
        'sync-events',
      );
      this.logger.log(
        'Successfully subscribed to Redis channel: agenda-updates',
      );
    } catch (err) {
      this.logger.error(
        'Failed to subscribe to Redis channel: agenda-updates',
        err,
      );
    }
  }

  private handleIncomingMessage(channel: string, message: string) {
    try {
      this.logger.log(`Received message from Redis on channel '${channel}'`);

      // FIX: We parse the JSON, but the result is initially 'unknown'.
      const unknownPayload: unknown = JSON.parse(message);
      // We emit the channel name as the event, which now includes our check-in stream
      this.eventEmitter.emit(channel, unknownPayload);
    } catch (error) {
      this.logger.error(
        `Failed to process incoming message from channel '${channel}': ${getErrorMessage(error)}`,
        message,
      );
    }
  }
}
