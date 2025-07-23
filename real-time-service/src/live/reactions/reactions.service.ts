import { Inject, Injectable } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/services/idempotency.service';
import { PublisherService } from 'src/shared/services/publisher.service';

/**
 * Service to handle user reactions (emojis) in live sessions.
 *
 * Usage:
 * - Call `addReaction` to increment emoji counts and publish reaction events.
 */
@Injectable()
export class ReactionsService {
  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly publisherService: PublisherService,
  ) {}

  /**
   * Atomically increments the count for a given emoji in a session's reactions.
   * Also publishes the reaction event for further processing.
   *
   * @param sessionId - The ID of the session where reaction was made.
   * @param userId - The user who reacted.
   * @param emoji - The emoji character representing the reaction.
   * @returns Promise<void>
   */
  async addReaction(
    sessionId: string,
    userId: string,
    emoji: string,
  ): Promise<void> {
    const redisKey = `reactions:${sessionId}`;

    // Increment the count of the emoji atomically in Redis hash
    await this.redis.hincrby(redisKey, emoji, 1);

    // Set expiration to clean up reaction data after 5 minutes of inactivity
    await this.redis.expire(redisKey, 300);

    // Publish the reaction event for downstream consumers
    const reactionPayload = {
      userId,
      sessionId,
      emoji,
      timestamp: new Date().toISOString(),
    };

    void this.publisherService.publish(
      'platform.events.live.reaction.v1',
      reactionPayload,
    );
  }
}
