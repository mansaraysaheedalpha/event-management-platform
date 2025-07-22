import { Inject, Injectable } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/services/idempotency.service';
import { PublisherService } from 'src/shared/services/publisher.service';

@Injectable()
export class ReactionsService {
  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly publisherService: PublisherService,
  ) {}

  /**
   * Atomically increments the count for a given emoji in a session's reaction hash.
   * This is a "fire-and-forget" operation from the client's perspective.
   *
   * @param sessionId The session to which the reaction belongs.
   * @param emoji The emoji character sent by the user.
   */
  async addReaction(
    sessionId: string,
    userId: string,
    emoji: string,
  ): Promise<void> {
    const redisKey = `reactions:${sessionId}`;
    // HINCRBY is an atomic "hash-increment-by" command. It's extremely fast.
    await this.redis.hincrby(redisKey, emoji, 1);
    // We also set an expiration on the hash key itself, so that if a session
    // becomes inactive, its reaction data will automatically be cleaned up from Redis.
    await this.redis.expire(redisKey, 300); // Expires after 5 minutes of inactivity

    // --- NEW: PUBLISH EVERY REACTION TO THE STREAM ---
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
