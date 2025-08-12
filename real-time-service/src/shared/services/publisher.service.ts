//src/shared/services/publisher.service.ts
import { Inject, Injectable, Logger } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from '../redis.constants';

@Injectable()
export class PublisherService {
  private readonly logger = new Logger(PublisherService.name);

  constructor(@Inject(REDIS_CLIENT) private readonly redis: Redis) {}

  /**
   * Publishes an event to a Redis Stream.
   *
   * @param stream The name of the stream (e.g., 'platform.events.chat.message.v1').
   * @param payload The data payload for the event.
   *  @returns Promise<void>
   */
  async publish(stream: string, payload: Record<string, any>) {
    try {
      // Redis Streams works with flat key-value pairs.
      // We'll stringify the payload to send it as a single 'data' field.
      const dataString = JSON.stringify(payload);

      // XADD is the command to add a new entry to a stream.
      // '*' tells Redis to auto-generate a unique ID for the entry.
      await this.redis.xadd(stream, '*', 'data', dataString);
      this.logger.log(`Published event to stream '${stream}'`);
    } catch (error) {
      this.logger.error(`Failed to publish event to stream '${stream}'`, error);
    }
  }
}
