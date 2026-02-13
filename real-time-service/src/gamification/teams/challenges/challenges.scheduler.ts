// src/gamification/teams/challenges/challenges.scheduler.ts
import { Inject, Injectable, Logger, OnModuleDestroy } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { ChallengesGateway } from './challenges.gateway';

const POLL_INTERVAL_MS = 5000; // Check every 5 seconds

@Injectable()
export class ChallengesScheduler implements OnModuleDestroy {
  private readonly logger = new Logger(ChallengesScheduler.name);
  private intervalId: NodeJS.Timeout | null = null;

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly challengesGateway: ChallengesGateway,
  ) {
    // Start polling for expired challenges
    this.intervalId = setInterval(() => {
      void this._checkExpiredChallenges();
    }, POLL_INTERVAL_MS);

    this.logger.log(
      `ChallengesScheduler started. Polling every ${POLL_INTERVAL_MS}ms.`,
    );
  }

  onModuleDestroy() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    this.logger.log('ChallengesScheduler stopped.');
  }

  /**
   * Scans all active challenge Redis hashes and completes any that have expired.
   * Uses SCAN to find all `challenge:active:*` keys.
   */
  private async _checkExpiredChallenges() {
    try {
      const keys = await this._scanKeys('challenge:active:*');
      const now = new Date();

      for (const key of keys) {
        const activeChallenges = await this.redis.hgetall(key);
        // Extract sessionId from key: challenge:active:{sessionId}
        const sessionId = key.replace('challenge:active:', '');

        for (const [challengeId, dataStr] of Object.entries(
          activeChallenges,
        )) {
          try {
            const data = JSON.parse(dataStr);
            const endTime = new Date(data.endTime);

            if (endTime <= now) {
              this.logger.log(
                `Challenge ${challengeId} expired. Completing...`,
              );
              await this.challengesGateway.completeAndBroadcast(
                sessionId,
                challengeId,
              );
            }
          } catch (parseError) {
            this.logger.warn(
              `Failed to parse challenge data for ${challengeId}: ${parseError}`,
            );
          }
        }
      }
    } catch (error) {
      this.logger.error(
        `ChallengesScheduler check failed: ${error?.message || error}`,
      );
    }
  }

  /**
   * Scans Redis keys matching a pattern. Uses SCAN to avoid blocking.
   */
  private async _scanKeys(pattern: string): Promise<string[]> {
    const keys: string[] = [];
    let cursor = '0';

    do {
      const [nextCursor, batch] = await this.redis.scan(
        cursor,
        'MATCH',
        pattern,
        'COUNT',
        100,
      );
      cursor = nextCursor;
      keys.push(...batch);
    } while (cursor !== '0');

    return keys;
  }
}
