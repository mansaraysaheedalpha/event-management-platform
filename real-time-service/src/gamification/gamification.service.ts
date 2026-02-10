//src/gamification/gamification.service.ts
import { Injectable, Logger, Inject } from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { PointReason, Prisma } from '@prisma/client';
import { GamificationGateway } from './gamification.gateway';
import { forwardRef } from '@nestjs/common';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/redis.constants';

// ============================================================
// Achievement Definitions (15 total, organized by category)
// ============================================================
export interface AchievementDefinition {
  badgeName: string;
  description: string;
  icon: string;
  category: string;
  trigger: string;
  condition: { count?: number; minPoints?: number };
  crossSession?: boolean;
}

export const ACHIEVEMENTS: Record<string, AchievementDefinition> = {
  // --- Social Butterfly (Chat) ---
  FIRST_WORDS: {
    badgeName: 'First Words',
    description: 'Sent your first chat message!',
    icon: '💬',
    category: 'Social Butterfly',
    trigger: 'MESSAGE_SENT',
    condition: { count: 1 },
  },
  CONVERSATION_STARTER: {
    badgeName: 'Conversation Starter',
    description: 'Sent 10 messages in a session!',
    icon: '🗣️',
    category: 'Social Butterfly',
    trigger: 'MESSAGE_SENT',
    condition: { count: 10 },
  },
  SOCIAL_BUTTERFLY: {
    badgeName: 'Social Butterfly',
    description: 'Sent 25 messages in a session!',
    icon: '🦋',
    category: 'Social Butterfly',
    trigger: 'MESSAGE_SENT',
    condition: { count: 25 },
  },

  // --- Curious Mind (Q&A) ---
  QUESTION_ASKER: {
    badgeName: 'Question Asker',
    description: 'Asked your first question!',
    icon: '❓',
    category: 'Curious Mind',
    trigger: 'QUESTION_ASKED',
    condition: { count: 1 },
  },
  THOUGHT_LEADER: {
    badgeName: 'Thought Leader',
    description: 'Asked 5 questions in a session!',
    icon: '🧠',
    category: 'Curious Mind',
    trigger: 'QUESTION_ASKED',
    condition: { count: 5 },
  },
  HELPFUL_HAND: {
    badgeName: 'Helpful Hand',
    description: 'Upvoted 10 questions!',
    icon: '🤝',
    category: 'Curious Mind',
    trigger: 'QUESTION_UPVOTED',
    condition: { count: 10 },
  },

  // --- Voice of the People (Polls) ---
  POLL_PIONEER: {
    badgeName: 'Poll Pioneer',
    description: 'Voted in your first poll!',
    icon: '🗳️',
    category: 'Voice of the People',
    trigger: 'POLL_VOTED',
    condition: { count: 1 },
  },
  SUPER_VOTER: {
    badgeName: 'Super Voter',
    description: 'Voted in 5 polls!',
    icon: '🏆',
    category: 'Voice of the People',
    trigger: 'POLL_VOTED',
    condition: { count: 5 },
  },
  OPINION_LEADER: {
    badgeName: 'Opinion Leader',
    description: 'Voted in 10 polls!',
    icon: '📊',
    category: 'Voice of the People',
    trigger: 'POLL_VOTED',
    condition: { count: 10 },
  },

  // --- Team Player ---
  TEAM_FOUNDER: {
    badgeName: 'Team Founder',
    description: 'Created a team!',
    icon: '🚀',
    category: 'Team Player',
    trigger: 'TEAM_CREATED',
    condition: { count: 1 },
  },
  TEAM_PLAYER: {
    badgeName: 'Team Player',
    description: 'Joined a team!',
    icon: '🤜',
    category: 'Team Player',
    trigger: 'TEAM_JOINED',
    condition: { count: 1 },
  },

  // --- Event Explorer ---
  EXPLORER: {
    badgeName: 'Explorer',
    description: 'Joined 3 different sessions!',
    icon: '🧭',
    category: 'Event Explorer',
    trigger: 'SESSION_JOINED',
    condition: { count: 3 },
    crossSession: true,
  },

  // --- Points Milestones ---
  ENGAGED_ATTENDEE: {
    badgeName: 'Engaged Attendee',
    description: 'Earned 50 points!',
    icon: '⭐',
    category: 'Milestones',
    trigger: 'POINTS_TOTAL',
    condition: { minPoints: 50 },
  },
  RISING_STAR: {
    badgeName: 'Rising Star',
    description: 'Earned 100 points!',
    icon: '🌟',
    category: 'Milestones',
    trigger: 'POINTS_TOTAL',
    condition: { minPoints: 100 },
  },
  SUPERSTAR: {
    badgeName: 'Superstar',
    description: 'Earned 200 points!',
    icon: '💫',
    category: 'Milestones',
    trigger: 'POINTS_TOTAL',
    condition: { minPoints: 200 },
  },
};

// Define the points awarded for each action
const POINT_VALUES: Record<PointReason, number> = {
  MESSAGE_SENT: 1,
  MESSAGE_REACTED: 2,
  QUESTION_ASKED: 5,
  QUESTION_UPVOTED: 2,
  POLL_CREATED: 10,
  POLL_VOTED: 1,
  WAITLIST_JOINED: 3,
  TEAM_CREATED: 5,
  TEAM_JOINED: 3,
  SESSION_JOINED: 2,
};

// Streak configuration
const STREAK_TTL_SECONDS = 300; // 5 minutes of inactivity resets streak
const STREAK_INCREMENT_COOLDOWN_MS = 60_000; // 1 minute between streak increments

@Injectable()
export class GamificationService {
  private readonly logger = new Logger(GamificationService.name);

  constructor(
    private readonly prisma: PrismaService,
    @Inject(forwardRef(() => GamificationGateway))
    private readonly gamificationGateway: GamificationGateway,
    @Inject(REDIS_CLIENT)
    private readonly redis: Redis,
  ) {}

  /**
   * Awards points to a user for a specific action and returns their new total score.
   * Includes streak multiplier for sustained engagement.
   */
  async awardPoints(
    userId: string,
    sessionId: string,
    reason: PointReason,
  ): Promise<number> {
    let pointsToAward = POINT_VALUES[reason];
    if (!pointsToAward) {
      this.logger.warn(`No point value defined for reason: ${reason}`);
      return 0;
    }

    try {
      // Check and update streak, apply multiplier
      const streak = await this._updateStreak(userId, sessionId);
      const multipliedPoints = Math.round(pointsToAward * streak.multiplier);

      const totalScore = await this.prisma.$transaction(async (tx) => {
        await tx.gamificationPointEntry.upsert({
          where: {
            userId_sessionId_reason: { userId, sessionId, reason },
          },
          update: {
            points: { increment: multipliedPoints },
            actionCount: { increment: 1 },
          },
          create: {
            userId,
            sessionId,
            reason,
            points: multipliedPoints,
            actionCount: 1,
          },
        });
        const aggregate = await tx.gamificationPointEntry.aggregate({
          _sum: { points: true },
          where: { userId, sessionId },
        });
        return aggregate._sum.points || 0;
      });

      // Send private notification to the user
      this.gamificationGateway.sendPointsAwardedNotification(userId, {
        points: multipliedPoints,
        basePoints: pointsToAward,
        reason: reason,
        newTotalScore: totalScore,
        streakMultiplier: streak.multiplier,
        streakCount: streak.count,
      });

      // If streak status changed, notify the user
      if (streak.changed) {
        this.gamificationGateway.sendStreakNotification(userId, {
          count: streak.count,
          multiplier: streak.multiplier,
          active: streak.active,
        });
      }

      void this._checkAndGrantAchievements(
        userId,
        sessionId,
        totalScore,
        reason,
      );
      void this.gamificationGateway.broadcastLeaderboardUpdate(sessionId);
      return totalScore;
    } catch (error) {
      this.logger.error(
        `Failed to award points to user ${userId}:`,
        getErrorMessage(error),
      );
      const aggregate = await this.prisma.gamificationPointEntry.aggregate({
        _sum: { points: true },
        where: { userId, sessionId },
      });
      return aggregate._sum.points || 0;
    }
  }

  /**
   * Gets all achievements a user has unlocked.
   */
  async getUserAchievements(userId: string) {
    return this.prisma.gamificationAchievement.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
    });
  }

  /**
   * Gets the user's progress toward all achievements in a session.
   */
  async getAchievementProgress(userId: string, sessionId: string) {
    // Get user's existing badges
    const existingBadges = (
      await this.prisma.gamificationAchievement.findMany({
        where: { userId },
        select: { badgeName: true, createdAt: true },
      })
    ).reduce(
      (map, b) => {
        map[b.badgeName] = b.createdAt;
        return map;
      },
      {} as Record<string, Date>,
    );

    // Get user's point entries for this session
    const pointEntries = await this.prisma.gamificationPointEntry.findMany({
      where: { userId, sessionId },
      select: { reason: true, points: true, actionCount: true },
    });

    const pointsMap = new Map<string, number>();
    const actionCountMap = new Map<string, number>();
    for (const entry of pointEntries) {
      pointsMap.set(entry.reason, entry.points);
      actionCountMap.set(entry.reason, entry.actionCount);
    }

    // Calculate total session score
    const totalScore = Array.from(pointsMap.values()).reduce(
      (sum, p) => sum + p,
      0,
    );

    // For cross-session achievements (like Explorer), count rows across all sessions
    const crossSessionCounts = new Map<string, number>();
    const crossSessionReasons = Object.values(ACHIEVEMENTS)
      .filter((a) => a.crossSession)
      .map((a) => a.trigger);

    if (crossSessionReasons.length > 0) {
      for (const reason of crossSessionReasons) {
        const count = await this.prisma.gamificationPointEntry.count({
          where: { userId, reason: reason as PointReason },
        });
        crossSessionCounts.set(reason, count);
      }
    }

    // Build progress for each achievement
    const progress = Object.entries(ACHIEVEMENTS).map(([key, achievement]) => {
      const isUnlocked = !!existingBadges[achievement.badgeName];
      const unlockedAt = existingBadges[achievement.badgeName] || null;

      let current = 0;
      let target = 0;

      if (achievement.trigger === 'POINTS_TOTAL') {
        current = totalScore;
        target = achievement.condition.minPoints || 0;
      } else if (achievement.crossSession) {
        current = crossSessionCounts.get(achievement.trigger) || 0;
        target = achievement.condition.count || 0;
      } else {
        current = actionCountMap.get(achievement.trigger) || 0;
        target = achievement.condition.count || 0;
      }

      return {
        key,
        badgeName: achievement.badgeName,
        description: achievement.description,
        icon: achievement.icon,
        category: achievement.category,
        isUnlocked,
        unlockedAt,
        current: Math.min(current, target),
        target,
        percentage: target > 0 ? Math.min((current / target) * 100, 100) : 0,
      };
    });

    return progress;
  }

  /**
   * Gets user stats for a session.
   */
  async getUserStats(userId: string, sessionId: string) {
    const totalPoints = await this.prisma.gamificationPointEntry.aggregate({
      _sum: { points: true },
      where: { userId, sessionId },
    });

    const achievementCount = await this.prisma.gamificationAchievement.count({
      where: { userId },
    });

    // Get rank
    const userScores = await this.prisma.gamificationPointEntry.groupBy({
      by: ['userId'],
      where: { sessionId },
      _sum: { points: true },
      orderBy: { _sum: { points: 'desc' } },
    });

    const rank =
      userScores.findIndex((s) => s.userId === userId) + 1 || null;

    // Get streak info from Redis
    const streakKey = `streak:${sessionId}:${userId}`;
    const streakVal = await this.redis.get(streakKey);
    const streakCount = streakVal ? parseInt(streakVal) : 0;
    const multiplier =
      streakCount >= 6 ? 2.0 : streakCount >= 3 ? 1.5 : 1.0;

    return {
      totalPoints: totalPoints._sum.points || 0,
      rank,
      achievementCount,
      totalAchievements: Object.keys(ACHIEVEMENTS).length,
      streak: {
        count: streakCount,
        multiplier,
        active: streakCount > 0,
      },
    };
  }

  /**
   * Calculates and returns the leaderboard for a given session.
   */
  async getLeaderboard(sessionId: string, currentUserId?: string, limit = 10) {
    const userScores = await this.prisma.gamificationPointEntry.groupBy({
      by: ['userId'],
      where: { sessionId },
      _sum: { points: true },
      orderBy: { _sum: { points: 'desc' } },
    });

    const topUserIds = userScores
      .slice(0, limit)
      .map((score) => score.userId);
    const topUsers = await this.prisma.userReference.findMany({
      where: { id: { in: topUserIds } },
      select: { id: true, firstName: true, lastName: true },
    });

    const userMap = new Map(topUsers.map((user) => [user.id, user]));

    const topEntries = userScores.slice(0, limit).map((score, index) => ({
      rank: index + 1,
      user: userMap.get(score.userId),
      score: score._sum.points || 0,
    }));

    let currentUserData: { rank: number | null; score: number } | null = null;
    if (currentUserId) {
      const currentUserRank =
        userScores.findIndex((score) => score.userId === currentUserId) + 1;
      const currentUserScore =
        userScores.find((score) => score.userId === currentUserId)?._sum
          .points || 0;

      currentUserData = {
        rank: currentUserRank > 0 ? currentUserRank : null,
        score: currentUserScore,
      };
    }

    return {
      topEntries,
      currentUser: currentUserData,
    };
  }

  /**
   * Calculates and returns the team leaderboard for a given session.
   */
  async getTeamLeaderboard(sessionId: string, limit = 10) {
    const teamsWithScores = await this.prisma.team.findMany({
      where: { sessionId },
      include: {
        _count: { select: { members: true } },
        members: {
          include: {
            user: {
              include: {
                gamificationPointEntries: {
                  where: { sessionId },
                  select: { points: true },
                },
              },
            },
          },
        },
      },
    });

    const teamScores = teamsWithScores.map((team) => {
      const totalScore = team.members.reduce((sum, member) => {
        const userScore = member.user.gamificationPointEntries.reduce(
          (userSum, entry) => userSum + entry.points,
          0,
        );
        return sum + userScore;
      }, 0);

      return {
        teamId: team.id,
        name: team.name,
        memberCount: team._count.members,
        score: totalScore,
      };
    });

    return teamScores
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map((team, index) => ({ ...team, rank: index + 1 }));
  }

  /**
   * Updates the user's engagement streak and returns current streak info.
   * Streak increments at most once per minute to reward sustained engagement.
   */
  private async _updateStreak(
    userId: string,
    sessionId: string,
  ): Promise<{
    count: number;
    multiplier: number;
    active: boolean;
    changed: boolean;
  }> {
    const streakKey = `streak:${sessionId}:${userId}`;
    const lastIncrementKey = `streak:ts:${sessionId}:${userId}`;

    try {
      const [streakVal, lastTs] = await Promise.all([
        this.redis.get(streakKey),
        this.redis.get(lastIncrementKey),
      ]);

      const now = Date.now();
      const previousCount = streakVal ? parseInt(streakVal) : 0;
      const canIncrement =
        !lastTs || now - parseInt(lastTs) >= STREAK_INCREMENT_COOLDOWN_MS;

      if (canIncrement) {
        const newCount = previousCount + 1;
        const pipeline = this.redis.pipeline();
        pipeline.setex(streakKey, STREAK_TTL_SECONDS, newCount.toString());
        pipeline.setex(
          lastIncrementKey,
          STREAK_TTL_SECONDS,
          now.toString(),
        );
        await pipeline.exec();

        const prevMultiplier =
          previousCount >= 6 ? 2.0 : previousCount >= 3 ? 1.5 : 1.0;
        const newMultiplier =
          newCount >= 6 ? 2.0 : newCount >= 3 ? 1.5 : 1.0;

        return {
          count: newCount,
          multiplier: newMultiplier,
          active: true,
          changed: prevMultiplier !== newMultiplier,
        };
      } else {
        // Just refresh TTLs without incrementing
        const pipeline = this.redis.pipeline();
        pipeline.expire(streakKey, STREAK_TTL_SECONDS);
        pipeline.expire(lastIncrementKey, STREAK_TTL_SECONDS);
        await pipeline.exec();

        const multiplier =
          previousCount >= 6 ? 2.0 : previousCount >= 3 ? 1.5 : 1.0;

        return {
          count: previousCount,
          multiplier,
          active: previousCount > 0,
          changed: false,
        };
      }
    } catch (error) {
      this.logger.warn(`Streak update failed: ${getErrorMessage(error)}`);
      return { count: 0, multiplier: 1.0, active: false, changed: false };
    }
  }

  /**
   * Checks for and grants new achievements to a user based on their actions and score.
   * Fixed: Uses points/pointValue to calculate action count (not row count).
   */
  private async _checkAndGrantAchievements(
    userId: string,
    sessionId: string,
    totalScore: number,
    lastAction: PointReason,
  ) {
    const existingBadges = (
      await this.prisma.gamificationAchievement.findMany({
        where: { userId },
        select: { badgeName: true },
      })
    ).map((b) => b.badgeName);

    for (const key of Object.keys(ACHIEVEMENTS) as Array<
      keyof typeof ACHIEVEMENTS
    >) {
      const achievement = ACHIEVEMENTS[key];

      if (existingBadges.includes(achievement.badgeName)) {
        continue;
      }

      // Check score-based achievements
      if (
        achievement.trigger === 'POINTS_TOTAL' &&
        'minPoints' in achievement.condition &&
        totalScore >= achievement.condition.minPoints!
      ) {
        await this._grantAchievement(userId, achievement);
        continue;
      }

      // Only check action-based achievements for the matching trigger
      if (achievement.trigger !== lastAction) continue;

      if (achievement.crossSession) {
        // Cross-session: count distinct rows across all sessions
        const rowCount = await this.prisma.gamificationPointEntry.count({
          where: { userId, reason: lastAction },
        });
        if (
          'count' in achievement.condition &&
          rowCount >= achievement.condition.count!
        ) {
          await this._grantAchievement(userId, achievement);
        }
      } else {
        // Session-scoped: use tracked actionCount for accurate count
        const entry = await this.prisma.gamificationPointEntry.findUnique({
          where: {
            userId_sessionId_reason: { userId, sessionId, reason: lastAction },
          },
          select: { actionCount: true },
        });

        if (entry) {
          if (
            'count' in achievement.condition &&
            entry.actionCount >= achievement.condition.count!
          ) {
            await this._grantAchievement(userId, achievement);
          }
        }
      }
    }
  }

  /**
   * Grants a single achievement, ensuring no duplicates.
   */
  private async _grantAchievement(
    userId: string,
    achievement: AchievementDefinition,
  ) {
    try {
      const newAchievement = await this.prisma.gamificationAchievement.create({
        data: {
          userId,
          badgeName: achievement.badgeName,
          description: achievement.description,
        },
      });

      this.logger.log(
        `User ${userId} unlocked achievement: ${achievement.badgeName}`,
      );
      this.gamificationGateway.sendAchievementNotification(userId, {
        ...newAchievement,
        icon: achievement.icon,
        category: achievement.category,
      });
    } catch (error) {
      if (
        error instanceof Prisma.PrismaClientKnownRequestError &&
        error.code === 'P2002'
      ) {
        return;
      }
      this.logger.error(
        `Failed to grant achievement to user ${userId}`,
        getErrorMessage(error),
      );
    }
  }
}
