// src/gamification/teams/synergy/synergy.service.ts
import { Inject, Injectable, Logger } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { PrismaService } from 'src/prisma.service';

const ACTIVE_TTL_SECONDS = 300; // 5 minutes
const MAX_SYNERGY_MULTIPLIER = 1.3;

// Uses a Redis SET per team instead of individual keys + KEYS scan.
// SET key: `team:active:{sessionId}:{teamId}`
// Members: userId strings. Each SADD refreshes TTL on the set.
const ACTIVE_SET_KEY = (sessionId: string, teamId: string) =>
  `team:active:${sessionId}:${teamId}`;

@Injectable()
export class SynergyService {
  private readonly logger = new Logger(SynergyService.name);

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly prisma: PrismaService,
  ) {}

  /**
   * Marks a user as active for their team in this session.
   * Uses SADD + EXPIRE on a team-level SET (O(1) operations).
   */
  async markActive(
    userId: string,
    sessionId: string,
    teamId: string,
  ): Promise<void> {
    const key = ACTIVE_SET_KEY(sessionId, teamId);
    const pipeline = this.redis.pipeline();
    pipeline.sadd(key, userId);
    pipeline.expire(key, ACTIVE_TTL_SECONDS);
    await pipeline.exec();
  }

  /**
   * Counts the number of currently active teammates (excluding the given user).
   * Uses SCARD - SISMEMBER for O(1) counting (no KEYS scan).
   */
  async getActiveTeammateCount(
    userId: string,
    sessionId: string,
    teamId: string,
  ): Promise<number> {
    const key = ACTIVE_SET_KEY(sessionId, teamId);
    const [totalMembers, isSelfActive] = await Promise.all([
      this.redis.scard(key),
      this.redis.sismember(key, userId),
    ]);
    // Subtract 1 if the user themselves is in the set
    return Math.max(0, totalMembers - (isSelfActive ? 1 : 0));
  }

  /**
   * Returns the synergy multiplier based on active teammates.
   * 0 active teammates -> 1.0x (no bonus)
   * 1 active teammate  -> 1.1x
   * 2 active teammates -> 1.2x
   * 3+ active teammates -> 1.3x (capped)
   */
  getSynergyMultiplier(activeTeammateCount: number): number {
    if (activeTeammateCount <= 0) return 1.0;
    if (activeTeammateCount === 1) return 1.1;
    if (activeTeammateCount === 2) return 1.2;
    return MAX_SYNERGY_MULTIPLIER;
  }

  /**
   * Full synergy check: finds the user's team, marks them active,
   * counts active teammates, returns the multiplier.
   * Returns { teamId, multiplier, activeTeammates } or null if user is not in a team.
   */
  async computeSynergy(
    userId: string,
    sessionId: string,
  ): Promise<{
    teamId: string;
    multiplier: number;
    activeTeammates: number;
  } | null> {
    try {
      // Find the user's team in this session
      const membership = await this.prisma.teamMembership.findFirst({
        where: {
          userId,
          team: { sessionId },
        },
        select: { teamId: true },
      });

      if (!membership) return null;

      const { teamId } = membership;

      // Mark user as active
      await this.markActive(userId, sessionId, teamId);

      // Count active teammates
      const activeTeammates = await this.getActiveTeammateCount(
        userId,
        sessionId,
        teamId,
      );

      const multiplier = this.getSynergyMultiplier(activeTeammates);

      return { teamId, multiplier, activeTeammates };
    } catch (error) {
      this.logger.warn(
        `Synergy computation failed for user ${userId}: ${error?.message || error}`,
      );
      return null;
    }
  }
}
