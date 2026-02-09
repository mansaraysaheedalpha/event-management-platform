//src/monetization/waitlist/waitlist.service.ts
import { ConflictException, Inject, Injectable, Logger, forwardRef } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { MonetizationGateway } from '../ads/monetization.gateway';
import { GamificationService } from 'src/gamification/gamification.service';

/**
 * The `WaitlistService` manages a FIFO waitlist for event sessions using Redis.
 * It allows users to be added to or retrieved from the waitlist for a session.
 *
 * This service supports use cases like handling full sessions where users are
 * placed in a queue and notified when a spot opens up.
 *
 * @remarks
 * Waitlists can grow unbounded if sessions are abandoned. Redis keys persist indefinitely unless explicitly expired or deleted.
 * Implement cleanup or TTL strategies to avoid resource leaks and stale data.
 *
 * @example
 * // Add a user to waitlist
 * await waitlistService.addUserToWaitlist('session-123', 'user-456');
 *
 * // Get the next user when a spot is available
 * const nextUser = await waitlistService.getNextUserFromWaitlist('session-123');
 */
@Injectable()
export class WaitlistService {
  /** Compile-time constant for waitlist Redis key prefix */
  private static readonly WAITLIST_KEY_PREFIX = 'waitlist:';
  private readonly logger = new Logger(WaitlistService.name);

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly idempotencyService: IdempotencyService,
    @Inject(forwardRef(() => MonetizationGateway))
    private readonly gateway: MonetizationGateway,
    private readonly gamificationService: GamificationService,
  ) {}

  /**
   * Builds a Redis key for the waitlist associated with a session.
   *
   * @param sessionId - The unique ID of the session
   * @returns The Redis key string for the session's waitlist
   */
  private getRedisKey(sessionId: string): string {
    return `${WaitlistService.WAITLIST_KEY_PREFIX}${sessionId}`;
  }

  /**
   * Adds a user to the end of the waitlist for a given session.
   * Redis `RPUSH` ensures FIFO order is maintained.
   * Emits position updates to all users in the waitlist.
   *
   * @param sessionId - The ID of the session
   * @param userId - The ID of the user to be added
   * @returns Promise that resolves once the user is added
   */
  async addUserToWaitlist(
    sessionId: string,
    userId: string,
    idempotencyKey: string,
  ): Promise<void> {
    const canProceed =
      await this.idempotencyService.checkAndSet(idempotencyKey);
    if (!canProceed) {
      throw new ConflictException(
        'This waitlist join request has already been processed.',
      );
    }
    const redisKey = this.getRedisKey(sessionId);
    try {
      await this.redis.rpush(redisKey, userId);
      this.logger.log(
        `User ${userId} added to waitlist for session ${sessionId}`,
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
   * Retrieves and removes the next user from the front of the session waitlist.
   * Redis `LPOP` ensures atomic removal in FIFO order.
   * Emits position updates to remaining users in the waitlist.
   *
   * @param sessionId - The ID of the session
   * @returns The user ID if one exists, otherwise null
   */
  async getNextUserFromWaitlist(sessionId: string): Promise<string | null> {
    const redisKey = this.getRedisKey(sessionId);
    const userId = await this.redis.lpop(redisKey);
    if (userId) {
      this.logger.log(
        `User ${userId} popped from waitlist for session ${sessionId}`,
      );
    }
    // Check if the list is now empty and clean up the key
    const listLength = await this.redis.llen(redisKey);
    if (listLength === 0) {
      await this.redis.del(redisKey);
      this.logger.log(
        `Waitlist for session ${sessionId} is now empty and key deleted.`,
      );
    } else {
      // Optionally set an expiration to avoid stale keys
      await this.redis.expire(redisKey, 3600); // 1 hour
      this.logger.log(
        `Waitlist for session ${sessionId} still has users, expiration set.`,
      );

      // Emit position updates to remaining users
      await this.emitPositionUpdates(sessionId);
    }
    return userId;
  }

  /**
   * Emits position updates to all users currently in the waitlist.
   * This method fetches all user IDs in the queue and sends each user
   * their current position and estimated wait time.
   *
   * @param sessionId - The ID of the session
   * @returns Promise that resolves once updates are emitted
   */
  private async emitPositionUpdates(sessionId: string): Promise<void> {
    try {
      const redisKey = this.getRedisKey(sessionId);
      const userIds = await this.redis.lrange(redisKey, 0, -1);

      if (!userIds || userIds.length === 0) {
        return;
      }

      const totalInQueue = userIds.length;
      const userPositions = userIds.map((userId, index) => ({
        userId,
        position: index + 1, // Position is 1-indexed
      }));

      // Emit position updates via the gateway
      this.gateway.sendWaitlistPositionUpdate(
        userPositions,
        sessionId,
        totalInQueue,
      );

      this.logger.log(
        `Emitted position updates for ${totalInQueue} users in session ${sessionId}`,
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
   *
   * @param sessionId - The ID of the session
   * @param userId - The ID of the user to find
   * @returns The user's position (1-indexed) or null if not in waitlist
   */
  async getUserPosition(
    sessionId: string,
    userId: string,
  ): Promise<number | null> {
    const redisKey = this.getRedisKey(sessionId);
    const userIds = await this.redis.lrange(redisKey, 0, -1);
    const position = userIds.indexOf(userId);

    if (position === -1) {
      return null;
    }

    return position + 1; // Return 1-indexed position
  }

  /**
   * Gets the total number of users in the waitlist.
   *
   * @param sessionId - The ID of the session
   * @returns The total number of users waiting
   */
  async getWaitlistLength(sessionId: string): Promise<number> {
    const redisKey = this.getRedisKey(sessionId);
    return await this.redis.llen(redisKey);
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

      // Schedule expiration notification
      setTimeout(() => {
        this.handleOfferExpiration(userId, sessionId, offerToken);
      }, timeUntilExpiration);

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
   * This should be called after successful offer acceptance.
   *
   * @param sessionId - The ID of the session
   * @param userId - The ID of the user who accepted
   */
  async removeUserFromWaitlist(
    sessionId: string,
    userId: string,
  ): Promise<void> {
    const redisKey = this.getRedisKey(sessionId);
    try {
      await this.redis.lrem(redisKey, 1, userId);
      this.logger.log(
        `User ${userId} removed from waitlist for session ${sessionId}`,
      );

      // Emit position updates to remaining users
      await this.emitPositionUpdates(sessionId);
    } catch (err) {
      this.logger.error(
        `Failed to remove user ${userId} from waitlist`,
        err,
      );
    }
  }
}
