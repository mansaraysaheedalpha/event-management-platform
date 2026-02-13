// src/gamification/teams/challenges/challenges.service.ts
import {
  ConflictException,
  Inject,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { CreateChallengeDto } from './dto/create-challenge.dto';
import { ChallengeType, PointReason } from '@prisma/client';
import { CHALLENGE_TEMPLATES } from './challenge-templates';

// Redis key patterns for active challenge progress
const PROGRESS_KEY = (challengeId: string, teamId: string) =>
  `challenge:progress:${challengeId}:${teamId}`;
const ACTIVE_CHALLENGES_KEY = (sessionId: string) =>
  `challenge:active:${sessionId}`;

@Injectable()
export class ChallengesService {
  private readonly logger = new Logger(ChallengesService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
  ) {}

  /**
   * Returns the list of available challenge templates.
   */
  getTemplates() {
    return Object.entries(CHALLENGE_TEMPLATES).map(([key, template]) => ({
      key,
      ...template,
    }));
  }

  /**
   * Creates a new challenge in PENDING status.
   */
  async createChallenge(
    creatorId: string,
    sessionId: string,
    dto: CreateChallengeDto,
  ) {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException('This challenge has already been created.');
    }

    // Resolve trackedReason based on type if not explicitly provided
    let trackedReason = dto.trackedReason ?? null;
    if (!trackedReason && dto.type !== 'CUSTOM' && dto.type !== 'MULTI_ACTION') {
      const template = Object.values(CHALLENGE_TEMPLATES).find(
        (t) => t.type === dto.type,
      );
      trackedReason = template?.trackedReason ?? null;
    }

    const challenge = await this.prisma.teamChallenge.create({
      data: {
        sessionId,
        name: dto.name,
        description: dto.description,
        type: dto.type,
        durationMinutes: dto.durationMinutes,
        trackedReason,
        actionWeights: dto.actionWeights ?? undefined,
        rewardFirst: dto.rewardFirst ?? 50,
        rewardSecond: dto.rewardSecond ?? 30,
        rewardThird: dto.rewardThird ?? 15,
        createdById: creatorId,
      },
    });

    this.logger.log(
      `Challenge ${challenge.id} (${challenge.name}) created for session ${sessionId}`,
    );
    return challenge;
  }

  /**
   * Starts an existing challenge: transitions PENDING → ACTIVE, creates progress
   * rows for all teams in the session, and registers in Redis for tracking.
   */
  async startChallenge(challengeId: string) {
    const challenge = await this.prisma.teamChallenge.findUnique({
      where: { id: challengeId },
    });

    if (!challenge) {
      throw new NotFoundException(`Challenge ${challengeId} not found.`);
    }
    if (challenge.status !== 'PENDING') {
      throw new ConflictException(
        `Challenge is ${challenge.status}, not PENDING.`,
      );
    }

    const now = new Date();
    const endTime = new Date(
      now.getTime() + challenge.durationMinutes * 60 * 1000,
    );

    // Get all teams in the session
    const teams = await this.prisma.team.findMany({
      where: { sessionId: challenge.sessionId },
      select: { id: true },
    });

    // Use transaction: update challenge status + create progress rows
    const updated = await this.prisma.$transaction(async (tx) => {
      const updatedChallenge = await tx.teamChallenge.update({
        where: { id: challengeId },
        data: {
          status: 'ACTIVE',
          startedAt: now,
          endedAt: endTime,
        },
      });

      // Create progress entries for each team
      if (teams.length > 0) {
        await tx.teamChallengeProgress.createMany({
          data: teams.map((t) => ({
            challengeId,
            teamId: t.id,
            score: 0,
            actionCount: 0,
          })),
          skipDuplicates: true,
        });
      }

      return updatedChallenge;
    });

    // Initialize Redis progress counters and register challenge as active
    const pipeline = this.redis.pipeline();
    for (const team of teams) {
      pipeline.setex(
        PROGRESS_KEY(challengeId, team.id),
        challenge.durationMinutes * 60 + 60, // extra 60s buffer
        '0',
      );
    }

    // Register this challenge as active for the session
    // Store JSON: { challengeId, trackedReason, type, actionWeights, endTime }
    const activeData = JSON.stringify({
      challengeId,
      trackedReason: challenge.trackedReason,
      type: challenge.type,
      actionWeights: challenge.actionWeights,
      endTime: endTime.toISOString(),
    });
    pipeline.hset(
      ACTIVE_CHALLENGES_KEY(challenge.sessionId),
      challengeId,
      activeData,
    );
    await pipeline.exec();

    this.logger.log(
      `Challenge ${challengeId} started. Ends at ${endTime.toISOString()}. ${teams.length} teams competing.`,
    );

    return updated;
  }

  /**
   * Cancels an active or pending challenge.
   */
  async cancelChallenge(challengeId: string) {
    const challenge = await this.prisma.teamChallenge.findUnique({
      where: { id: challengeId },
    });
    if (!challenge) {
      throw new NotFoundException(`Challenge ${challengeId} not found.`);
    }
    if (challenge.status === 'COMPLETED' || challenge.status === 'CANCELLED') {
      throw new ConflictException(
        `Challenge is already ${challenge.status}.`,
      );
    }

    const updated = await this.prisma.teamChallenge.update({
      where: { id: challengeId },
      data: { status: 'CANCELLED', endedAt: new Date() },
    });

    // Clean up Redis
    await this.redis.hdel(
      ACTIVE_CHALLENGES_KEY(challenge.sessionId),
      challengeId,
    );

    this.logger.log(`Challenge ${challengeId} cancelled.`);
    return updated;
  }

  /**
   * Called by the action event listener. Checks if there are active challenges
   * in the session that track this action, and increments team progress.
   * Returns progress data for broadcasting.
   */
  async trackAction(
    sessionId: string,
    teamId: string,
    reason: PointReason,
  ): Promise<
    Array<{
      challengeId: string;
      teamId: string;
      score: number;
    }>
  > {
    if (!teamId) return [];

    // Get all active challenges for this session from Redis
    const activeChallenges = await this.redis.hgetall(
      ACTIVE_CHALLENGES_KEY(sessionId),
    );
    if (!activeChallenges || Object.keys(activeChallenges).length === 0) {
      return [];
    }

    const results: Array<{
      challengeId: string;
      teamId: string;
      score: number;
    }> = [];

    for (const [challengeId, dataStr] of Object.entries(activeChallenges)) {
      const data = JSON.parse(dataStr);

      // Check if challenge has expired (scheduler will complete it, but skip tracking)
      if (new Date(data.endTime) < new Date()) continue;

      // Check if this action is tracked by this challenge
      let weight = 0;
      if (
        data.type === 'POINTS_RACE' ||
        data.type === 'MULTI_ACTION'
      ) {
        // Multi-action: check weights map, default 1 for all actions
        const weights = data.actionWeights as Record<string, number> | null;
        weight = weights?.[reason] ?? 1;
      } else if (data.trackedReason === reason) {
        weight = 1;
      }

      if (weight === 0) continue;

      // Increment score in Redis
      const progressKey = PROGRESS_KEY(challengeId, teamId);
      const newScore = await this.redis.incrby(progressKey, weight);

      results.push({ challengeId, teamId, score: newScore });
    }

    return results;
  }

  /**
   * Completes a challenge: persists final scores from Redis → DB,
   * ranks teams, and returns ranked results.
   *
   * Uses atomic HDEL as a distributed lock — if another process already
   * removed the challenge from the active hash, we bail out (returns null).
   */
  async completeChallenge(challengeId: string) {
    const challenge = await this.prisma.teamChallenge.findUnique({
      where: { id: challengeId },
      include: { progress: true },
    });

    if (!challenge) {
      throw new NotFoundException(`Challenge ${challengeId} not found.`);
    }

    // Atomic guard: HDEL returns the number of fields removed.
    // If 0, another process already claimed this challenge — bail out.
    const removed = await this.redis.hdel(
      ACTIVE_CHALLENGES_KEY(challenge.sessionId),
      challengeId,
    );
    if (removed === 0) {
      this.logger.warn(
        `Challenge ${challengeId} already claimed by another process. Skipping.`,
      );
      return null;
    }

    // Collect final scores from Redis
    const finalScores: Array<{ teamId: string; score: number }> = [];
    for (const prog of challenge.progress) {
      const key = PROGRESS_KEY(challengeId, prog.teamId);
      const scoreStr = await this.redis.get(key);
      const score = scoreStr ? parseInt(scoreStr) : 0;
      finalScores.push({ teamId: prog.teamId, score });
    }

    // Sort by score descending
    finalScores.sort((a, b) => b.score - a.score);

    // Persist to DB
    await this.prisma.$transaction(async (tx) => {
      // Update challenge status
      await tx.teamChallenge.update({
        where: { id: challengeId },
        data: {
          status: 'COMPLETED',
          endedAt: new Date(),
        },
      });

      // Update progress rows with final scores and ranks
      for (let i = 0; i < finalScores.length; i++) {
        const { teamId, score } = finalScores[i];
        await tx.teamChallengeProgress.update({
          where: {
            challengeId_teamId: { challengeId, teamId },
          },
          data: {
            score,
            actionCount: score,
            finalRank: i + 1,
          },
        });
      }
    });

    // Clean up remaining Redis progress keys
    const pipeline = this.redis.pipeline();
    for (const prog of challenge.progress) {
      pipeline.del(PROGRESS_KEY(challengeId, prog.teamId));
    }
    await pipeline.exec();

    this.logger.log(
      `Challenge ${challengeId} completed. Rankings: ${finalScores.map((s, i) => `#${i + 1} team ${s.teamId} (${s.score})`).join(', ')}`,
    );

    return {
      challenge,
      rankings: finalScores.map((s, i) => ({
        rank: i + 1,
        teamId: s.teamId,
        score: s.score,
      })),
    };
  }

  /**
   * Gets the current progress for all teams in an active challenge (from Redis).
   */
  async getActiveProgress(challengeId: string) {
    const challenge = await this.prisma.teamChallenge.findUnique({
      where: { id: challengeId },
      include: {
        progress: {
          include: {
            team: { select: { id: true, name: true } },
          },
        },
      },
    });

    if (!challenge) {
      throw new NotFoundException(`Challenge ${challengeId} not found.`);
    }

    const results: Array<{ teamId: string; teamName: string; score: number }> = [];
    for (const prog of challenge.progress) {
      const key = PROGRESS_KEY(challengeId, prog.teamId);
      const scoreStr = await this.redis.get(key);
      results.push({
        teamId: prog.teamId,
        teamName: prog.team.name,
        score: scoreStr ? parseInt(scoreStr) : 0,
      });
    }

    // Sort by score desc
    results.sort((a, b) => b.score - a.score);

    return {
      challengeId: challenge.id,
      name: challenge.name,
      type: challenge.type,
      status: challenge.status,
      startedAt: challenge.startedAt,
      endedAt: challenge.endedAt,
      durationMinutes: challenge.durationMinutes,
      teams: results.map((r, i) => ({ ...r, rank: i + 1 })),
    };
  }

  /**
   * Lists all challenges for a session (with optional status filter).
   */
  async listChallenges(sessionId: string, status?: string) {
    const where: any = { sessionId };
    if (status) {
      where.status = status;
    }

    return this.prisma.teamChallenge.findMany({
      where,
      include: {
        progress: {
          include: {
            team: { select: { id: true, name: true } },
          },
        },
      },
      orderBy: { createdAt: 'desc' },
    });
  }

  /**
   * Returns all active challenge IDs for a session (used by scheduler).
   */
  async getActiveChallengeIds(sessionId: string): Promise<string[]> {
    const challenges = await this.redis.hgetall(
      ACTIVE_CHALLENGES_KEY(sessionId),
    );
    return Object.keys(challenges);
  }
}
