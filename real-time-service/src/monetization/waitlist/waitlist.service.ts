import { Inject, Injectable, Logger } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/shared.module';

@Injectable()
export class WaitlistService {
  private readonly logger = new Logger(WaitlistService.name);

  constructor(@Inject(REDIS_CLIENT) private readonly redis: Redis) {}

  private getRedisKey(sessionId: string): string {
    return `waitlist:${sessionId}`;
  }

  /**
   * Adds a user to the end of the waitlist for a session.
   */
  async addUserToWaitlist(sessionId: string, userId: string): Promise<void> {
    const redisKey = this.getRedisKey(sessionId);
    await this.redis.rpush(redisKey, userId);
    this.logger.log(
      `User ${userId} added to waitlist for session ${sessionId}`,
    );
  }

  /**
   * Gets the next user from the front of the waitlist.
   * This is an atomic operation.
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
