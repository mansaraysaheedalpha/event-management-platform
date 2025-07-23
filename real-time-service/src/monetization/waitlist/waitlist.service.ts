import { Inject, Injectable, Logger } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/shared.module';

/**
 * The `WaitlistService` manages a FIFO waitlist for event sessions using Redis.
 * It allows users to be added to or retrieved from the waitlist for a session.
 *
 * This service supports use cases like handling full sessions where users are
 * placed in a queue and notified when a spot opens up.
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
  private readonly logger = new Logger(WaitlistService.name);

  constructor(@Inject(REDIS_CLIENT) private readonly redis: Redis) {}

  /**
   * Builds a Redis key for the waitlist associated with a session.
   *
   * @param sessionId - The unique ID of the session
   * @returns The Redis key string for the session's waitlist
   */
  private getRedisKey(sessionId: string): string {
    return `waitlist:${sessionId}`;
  }

  /**
   * Adds a user to the end of the waitlist for a given session.
   * Redis `RPUSH` ensures FIFO order is maintained.
   *
   * @param sessionId - The ID of the session
   * @param userId - The ID of the user to be added
   * @returns Promise that resolves once the user is added
   */
  async addUserToWaitlist(sessionId: string, userId: string): Promise<void> {
    const redisKey = this.getRedisKey(sessionId);
    await this.redis.rpush(redisKey, userId);
    this.logger.log(
      `User ${userId} added to waitlist for session ${sessionId}`,
    );
  }

  /**
   * Retrieves and removes the next user from the front of the session waitlist.
   * Redis `LPOP` ensures atomic removal in FIFO order.
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
    return userId;
  }
}
