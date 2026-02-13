//src/monetization/waitlist/waitlist.service.ts
import { ConflictException, Inject, Injectable, Logger, OnApplicationShutdown, forwardRef } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { MonetizationGateway } from '../ads/monetization.gateway';
import { GamificationService } from 'src/gamification/gamification.service';

/**
 * Priority tiers for waitlist ordering, checked in descending priority.
 * Must match the Python backend's tier names in waitlist.py.
 */
const PRIORITY_TIERS = ['vip', 'premium', 'standard'] as const;
type PriorityTier = (typeof PRIORITY_TIERS)[number];

/** TTL in seconds for waitlist Redis keys (24 hours, matching Python backend). */
const WAITLIST_TTL_SECONDS = 86400;

/**
 * The `WaitlistService` manages a priority-tiered waitlist for event sessions
 * using Redis Sorted Sets (ZSET).
 *
 * Uses the same data structure and key format as the Python event-lifecycle-service:
 *   Key:   `waitlist:session:{sessionId}:{tier}`
 *   Score: Unix timestamp (ms) for FIFO ordering within each tier
 *
 * Priority order: VIP > PREMIUM > STANDARD
 *
 * @example
 * await waitlistService.addUserToWaitlist('session-123', 'user-456', 'key', 'standard');
 * const nextUser = await waitlistService.getNextUserFromWaitlist('session-123');
 */
@Injectable()
export class WaitlistService implements OnApplicationShutdown {
  private readonly logger = new Logger(WaitlistService.name);
  private readonly pendingTimers = new Set<ReturnType<typeof setTimeout>>();

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly idempotencyService: IdempotencyService,
    @Inject(forwardRef(() => MonetizationGateway))
    private readonly gateway: MonetizationGateway,
    private readonly gamificationService: GamificationService,
  ) {}

  /**
   * Builds a Redis key for a specific tier queue of a session's waitlist.
   * Format matches the Python backend: `waitlist:session:{sessionId}:{tier}`
   */
  private getRedisKey(sessionId: string, tier: PriorityTier = 'standard'): string {
    return `waitlist:session:${sessionId}:${tier}`;
  }

  /**
   * Returns all three tier keys for a session in priority order.
   */
  private getAllTierKeys(sessionId: string): string[] {
    return PRIORITY_TIERS.map((tier) => this.getRedisKey(sessionId, tier));
  }

  /**
   * Adds a user to the waitlist for a given session using Redis ZADD.
   * Uses the current timestamp as the score for FIFO ordering within the tier.
   * The NX flag ensures a user is only added if not already present.
   *
   * @param sessionId - The ID of the session
   * @param userId - The ID of the user to be added
   * @param idempotencyKey - Key for idempotent request handling
   * @param tier - Priority tier (default: 'standard')
   */
  async addUserToWaitlist(
    sessionId: string,
    userId: string,
    idempotencyKey: string,
    tier: PriorityTier = 'standard',
  ): Promise<void> {
    const canProceed =
      await this.idempotencyService.checkAndSet(idempotencyKey);
    if (!canProceed) {
      throw new ConflictException(
        'This waitlist join request has already been processed.',
      );
    }
    const redisKey = this.getRedisKey(sessionId, tier);
    try {
      const score = Date.now();
      // NX: only add if member does not already exist
      await this.redis.zadd(redisKey, 'NX', score, userId);
      // Set TTL to match Python backend (24 hours)
      await this.redis.expire(redisKey, WAITLIST_TTL_SECONDS);
      this.logger.log(
        `User ${userId} added to waitlist for session ${sessionId} (tier: ${tier})`,
      );

      // Award gamification points for joining the waitlist
      void this.gamificationService.awardPoints(
        userId,
        sessionId,
        'WAITLIST_JOINED',
      );

      // Emit position updates to all users in the waitlist
      await this.emitPositionUpdates(sessionId);
    } catch (err) {
      const errorMsg =
        err instanceof Error ? `${err.message}\n${err.stack}` : String(err);
      this.logger.error(
        `Failed to add user ${userId} to waitlist for session ${sessionId}: ${errorMsg}`,
      );
      throw new Error(
        'Could not add user to waitlist. Please try again later.',
      );
    }
  }

  /**
   * Retrieves and removes the next user from the session waitlist.
   * Checks tiers in priority order: VIP -> PREMIUM -> STANDARD.
   * Within each tier, picks the member with the lowest score (earliest join).
   *
   * @param sessionId - The ID of the session
   * @returns The user ID if one exists, otherwise null
   */
  async getNextUserFromWaitlist(sessionId: string): Promise<string | null> {
    for (const tier of PRIORITY_TIERS) {
      const redisKey = this.getRedisKey(sessionId, tier);
      // Atomic pop: ZPOPMIN removes and returns the member with the lowest score
      const result = await this.redis.zpopmin(redisKey, 1);
      if (result && result.length >= 2) {
        // zpopmin returns [member, score, member, score, ...]
        const userId = result[0];
        this.logger.log(
          `User ${userId} popped from waitlist for session ${sessionId} (tier: ${tier})`,
        );

        // Clean up empty keys
        const remaining = await this.redis.zcard(redisKey);
        if (remaining === 0) {
          await this.redis.del(redisKey);
        }

        // Emit position updates to remaining users
        await this.emitPositionUpdates(sessionId);
        return userId;
      }
    }

    this.logger.log(
      `Waitlist for session ${sessionId} is empty across all tiers.`,
    );
    return null;
  }

  /**
   * Emits position updates to all users currently in the waitlist.
   * Aggregates across all tiers in priority order so that VIP users
   * appear before PREMIUM, who appear before STANDARD.
   *
   * @param sessionId - The ID of the session
   */
  private async emitPositionUpdates(sessionId: string): Promise<void> {
    try {
      const allUsers: { userId: string; position: number }[] = [];
      let globalPosition = 0;

      for (const tier of PRIORITY_TIERS) {
        const redisKey = this.getRedisKey(sessionId, tier);
        // ZRANGE returns members sorted by score (join time)
        const userIds = await this.redis.zrange(redisKey, 0, -1);
        for (const userId of userIds) {
          globalPosition++;
          allUsers.push({ userId, position: globalPosition });
        }
      }

      if (allUsers.length === 0) {
        return;
      }

      // Emit position updates via the gateway
      this.gateway.sendWaitlistPositionUpdate(
        allUsers,
        sessionId,
        allUsers.length,
      );

      this.logger.log(
        `Emitted position updates for ${allUsers.length} users in session ${sessionId}`,
      );
    } catch (err) {
      this.logger.error(
        `Failed to emit position updates for session ${sessionId}`,
        err,
      );
      // Don't throw - position updates are non-critical
    }
  }

  /**
   * Gets the current position of a specific user in the waitlist.
   * Position accounts for all higher-priority tiers.
   *
   * @param sessionId - The ID of the session
   * @param userId - The ID of the user to find
   * @returns The user's position (1-indexed) or null if not in waitlist
   */
  async getUserPosition(
    sessionId: string,
    userId: string,
  ): Promise<number | null> {
    let offset = 0;

    for (const tier of PRIORITY_TIERS) {
      const redisKey = this.getRedisKey(sessionId, tier);
      const rank = await this.redis.zrank(redisKey, userId);

      if (rank !== null) {
        return offset + rank + 1; // 1-indexed
      }

      // User not in this tier; add this tier's count to the offset
      const tierSize = await this.redis.zcard(redisKey);
      offset += tierSize;
    }

    return null;
  }

  /**
   * Gets the total number of users in the waitlist across all tiers.
   *
   * @param sessionId - The ID of the session
   * @returns The total number of users waiting
   */
  async getWaitlistLength(sessionId: string): Promise<number> {
    let total = 0;
    for (const tier of PRIORITY_TIERS) {
      const redisKey = this.getRedisKey(sessionId, tier);
      total += await this.redis.zcard(redisKey);
    }
    return total;
  }

  /**
   * Tracks an active offer with expiration time.
   * When the offer expires, sends WAITLIST_OFFER_EXPIRED event to the user.
   *
   * @param userId - The ID of the user who received the offer
   * @param sessionId - The ID of the session
   * @param expiresAt - ISO timestamp when the offer expires
   * @param offerToken - The unique token for this offer
   */
  async trackOfferExpiration(
    userId: string,
    sessionId: string,
    expiresAt: string,
    offerToken: string,
  ): Promise<void> {
    try {
      const expiresAtDate = new Date(expiresAt);
      const now = new Date();
      const timeUntilExpiration = expiresAtDate.getTime() - now.getTime();

      if (timeUntilExpiration <= 0) {
        // Already expired
        this.logger.warn(
          `Offer for user ${userId} in session ${sessionId} is already expired`,
        );
        return;
      }

      // Store offer in Redis with expiration
      const offerKey = `waitlist:offer:${offerToken}`;
      await this.redis.setex(
        offerKey,
        Math.ceil(timeUntilExpiration / 1000),
        JSON.stringify({ userId, sessionId, expiresAt }),
      );

      // Schedule expiration notification (tracked for cleanup on shutdown)
      const timer = setTimeout(() => {
        this.pendingTimers.delete(timer);
        this.handleOfferExpiration(userId, sessionId, offerToken);
      }, timeUntilExpiration);
      this.pendingTimers.add(timer);

      this.logger.log(
        `Tracking offer expiration for user ${userId} in session ${sessionId}, expires at ${expiresAt}`,
      );
    } catch (err) {
      this.logger.error(
        `Failed to track offer expiration for user ${userId}`,
        err,
      );
    }
  }

  /**
   * Handles offer expiration by emitting the WAITLIST_OFFER_EXPIRED event.
   * Only emits if the offer hasn't been accepted (checked in Redis).
   *
   * @param userId - The ID of the user
   * @param sessionId - The ID of the session
   * @param offerToken - The unique token for this offer
   */
  private async handleOfferExpiration(
    userId: string,
    sessionId: string,
    offerToken: string,
  ): Promise<void> {
    try {
      // Check if offer was accepted (token marked as used)
      const usedKey = `waitlist:offer:used:${offerToken}`;
      const wasAccepted = await this.redis.exists(usedKey);

      if (wasAccepted) {
        this.logger.log(
          `Offer for user ${userId} was accepted, skipping expiration notification`,
        );
        return;
      }

      // Emit expiration event
      this.gateway.sendWaitlistOfferExpired(
        userId,
        sessionId,
        'Your waitlist offer has expired. You have been moved back to the waitlist.',
      );

      this.logger.log(
        `Emitted offer expiration for user ${userId} in session ${sessionId}`,
      );

      // Clean up offer tracking in Redis
      const offerKey = `waitlist:offer:${offerToken}`;
      await this.redis.del(offerKey);
    } catch (err) {
      this.logger.error(
        `Failed to handle offer expiration for user ${userId}`,
        err,
      );
    }
  }

  /**
   * Removes user from waitlist when they accept an offer.
   * Searches all tiers since the caller may not know which tier the user is in.
   *
   * @param sessionId - The ID of the session
   * @param userId - The ID of the user who accepted
   */
  async removeUserFromWaitlist(
    sessionId: string,
    userId: string,
  ): Promise<void> {
    try {
      for (const tier of PRIORITY_TIERS) {
        const redisKey = this.getRedisKey(sessionId, tier);
        const removed = await this.redis.zrem(redisKey, userId);
        if (removed > 0) {
          this.logger.log(
            `User ${userId} removed from waitlist for session ${sessionId} (tier: ${tier})`,
          );
          break;
        }
      }

      // Emit position updates to remaining users
      await this.emitPositionUpdates(sessionId);
    } catch (err) {
      this.logger.error(
        `Failed to remove user ${userId} from waitlist`,
        err,
      );
    }
  }

  /**
   * Clears all pending offer expiration timers on application shutdown.
   * Prevents memory leaks from orphaned setTimeout references.
   */
  onApplicationShutdown(): void {
    this.logger.log(
      `Clearing ${this.pendingTimers.size} pending offer expiration timers`,
    );
    for (const timer of this.pendingTimers) {
      clearTimeout(timer);
    }
    this.pendingTimers.clear();
  }
}
