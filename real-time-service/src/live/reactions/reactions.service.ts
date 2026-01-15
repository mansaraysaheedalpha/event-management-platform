//src/live/reactions/reactions.servicea.ts
import { forwardRef, Inject, Injectable, Logger } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { PublisherService } from 'src/shared/services/publisher.service';
import { ReactionsGateway } from './reactions.gateway';
import { OnEvent } from '@nestjs/event-emitter';

/**
 * Service to handle user reactions (emojis) in live sessions.
 *
 * Usage:
 * - Call `addReaction` to increment emoji counts and publish reaction events.
 */
@Injectable()
export class ReactionsService {
  private readonly logger = new Logger(ReactionsService.name);

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly publisherService: PublisherService,
    @Inject(forwardRef(() => ReactionsGateway))
    private readonly reactionsGateway: ReactionsGateway,
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

    // Set expiration to clean up reaction data after 5 minutes of inactivity, only if not already set
    await this.redis.expire(redisKey, 300, 'NX');

    // --- HEATMAP TRACKING (uses Pub/Sub, not Streams) ---
    void this.redis.publish(
      'heatmap-events',
      JSON.stringify({ sessionId }),
    );
    // --- END HEATMAP LOGIC ---

    // Publish the reaction event for downstream consumers
    const reactionPayload = {
      userId,
      sessionId,
      emoji,
      timestamp: new Date().toISOString(),
    };

    try {
      await this.publisherService.publish(
        'platform.events.live.reaction.v1',
        reactionPayload,
      );
    } catch (error) {
      this.logger.error('Failed to publish reaction event', error);
    }
  }

  /**
   * Listens for sentiment analysis from the Oracle AI.
   */
  @OnEvent('oracle.predictions.sentiment.v1')
  handleMoodAnalytics(payload: { sessionId: string; analytics: any }) {
    this.logger.log(
      `Processing mood analytics for session: ${payload.sessionId}`,
    );
    this.reactionsGateway.broadcastMoodAnalytics(
      payload.sessionId,
      payload.analytics,
    );
  }
}
