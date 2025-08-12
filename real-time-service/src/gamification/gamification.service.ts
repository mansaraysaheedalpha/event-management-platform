//src/gamification/gamification.service.ts
import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { PointReason, Prisma } from '@prisma/client';
import { GamificationGateway } from './gamification.gateway';
import { forwardRef, Inject } from '@nestjs/common';
import { getErrorMessage } from 'src/common/utils/error.utils';

// Your new, superior, data-driven achievement definitions
const ACHIEVEMENTS = {
  FIRST_QUESTION: {
    badgeName: 'Question Asker',
    description: 'You asked your first question!',
    trigger: 'QUESTION_ASKED',
    condition: { count: 1 },
  },
  SCORE_50: {
    badgeName: 'Engaged Attendee',
    description: 'You earned 50 points!',
    trigger: 'POINTS_TOTAL',
    condition: { minPoints: 50 },
  },
  // We can easily add more here in the future
  SUPER_VOTER: {
    badgeName: 'Super Voter',
    description: 'You voted 5 times!',
    trigger: 'POLL_VOTED',
    condition: { count: 5 },
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
};

@Injectable()
export class GamificationService {
  private readonly logger = new Logger(GamificationService.name);

  constructor(
    private readonly prisma: PrismaService,
    // Use forwardRef to break circular dependency
    @Inject(forwardRef(() => GamificationGateway))
    private readonly gamificationGateway: GamificationGateway,
  ) {}

  /**
   * Awards points to a user for a specific action and returns their new total score.
   * @param userId The ID of the user to award points to.
   * @param sessionId The session where the action occurred.
   * @param reason The reason points are being awarded.
   * @returns The user's new total point score for the session.
   */
  async awardPoints(
    userId: string,
    sessionId: string,
    reason: PointReason,
  ): Promise<number> {
    const pointsToAward = POINT_VALUES[reason];
    if (!pointsToAward) {
      this.logger.warn(`No point value defined for reason: ${reason}`);
      return 0;
    }

    const totalScore = await this.prisma.$transaction(async (tx) => {
      await tx.gamificationPointEntry.create({
        data: { userId, sessionId, reason, points: pointsToAward },
      });
      const aggregate = await tx.gamificationPointEntry.aggregate({
        _sum: { points: true },
        where: { userId, sessionId },
      });
      return aggregate._sum.points || 0;
    });

    // After points are awarded, send a private notification to the user.
    this.gamificationGateway.sendPointsAwardedNotification(userId, {
      points: pointsToAward,
      reason: reason,
      newTotalScore: totalScore,
    });

    void this._checkAndGrantAchievements(userId, sessionId, totalScore, reason);
    void this.gamificationGateway.broadcastLeaderboardUpdate(sessionId);
    return totalScore;
  }

  /**
   * Calculates and returns the leaderboard for a given session.
   * @param sessionId The ID of the session.
   * @param currentUserId The ID of the user requesting the leaderboard, to include their rank.
   * @param limit The number of top users to return.
   * @returns An object containing the top entries and the current user's rank.
   */
  async getLeaderboard(sessionId: string, currentUserId?: string, limit = 10) {
    // 1. Aggregate points for all users in the session
    const userScores = await this.prisma.gamificationPointEntry.groupBy({
      by: ['userId'],
      where: { sessionId },
      _sum: {
        points: true,
      },
      orderBy: {
        _sum: {
          points: 'desc',
        },
      },
    });

    // 2. Fetch user details for the top entries
    const topUserIds = userScores.slice(0, limit).map((score) => score.userId);
    const topUsers = await this.prisma.userReference.findMany({
      where: { id: { in: topUserIds } },
      select: { id: true, firstName: true, lastName: true },
    });

    const userMap = new Map(topUsers.map((user) => [user.id, user]));

    // 3. Format the top entries with ranks and scores
    const topEntries = userScores.slice(0, limit).map((score, index) => ({
      rank: index + 1,
      user: userMap.get(score.userId),
      score: score._sum.points || 0,
    }));

    // 4. Find the current user's rank and score

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
   * This is a highly efficient query that avoids the N+1 problem.
   */
  async getTeamLeaderboard(sessionId: string, limit = 10) {
    // This single, advanced Prisma query does all the work:
    // 1. It finds all teams for the session.
    // 2. For each team, it goes through the members.
    // 3. For each member, it sums up all the points they've earned in this session.
    // 4. It sums up the scores of all members to get a total team score.
    const teamsWithScores = await this.prisma.team.findMany({
      where: { sessionId },
      include: {
        _count: {
          select: { members: true },
        },
        members: {
          include: {
            user: {
              include: {
                _count: {
                  select: {
                    gamificationPointEntries: {
                      where: { sessionId },
                    },
                  },
                },
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

    // Now we process the results in memory, which is extremely fast
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

    // Sort the teams by score and return the top entries
    return teamScores
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map((team, index) => ({ ...team, rank: index + 1 }));
  }

  /**
   * Checks for and grants new achievements to a user based on their actions and score.
   */
  private async _checkAndGrantAchievements(
    userId: string,
    sessionId: string,
    totalScore: number,
    lastAction: PointReason,
  ) {
    // Get all achievements the user already has to prevent re-checking
    const existingBadges = (
      await this.prisma.gamificationAchievement.findMany({
        where: { userId },
        select: { badgeName: true },
      })
    ).map((b) => b.badgeName);

    // Loop through all possible achievements
    for (const key of Object.keys(ACHIEVEMENTS) as Array<
      keyof typeof ACHIEVEMENTS
    >) {
      const achievement = ACHIEVEMENTS[key];

      // Skip if user already has this badge
      if (existingBadges.includes(achievement.badgeName)) {
        continue;
      }

      // Check score-based achievements
      if (
        achievement.trigger === 'POINTS_TOTAL' &&
        'minPoints' in achievement.condition &&
        totalScore >= achievement.condition.minPoints
      ) {
        await this._grantAchievement(userId, achievement);
      }

      // Check action-based achievements
      if (achievement.trigger === lastAction) {
        const actionCount = await this.prisma.gamificationPointEntry.count({
          where: { userId, sessionId, reason: lastAction },
        });

        if (
          'count' in achievement.condition &&
          actionCount >= achievement.condition.count
        ) {
          await this._grantAchievement(userId, achievement);
        }
      }
    }
  }
  /**
   * A private helper to grant a single achievement, ensuring no duplicates.
   */
  private async _grantAchievement(
    userId: string,
    achievement: { badgeName: string; description: string },
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
      this.gamificationGateway.sendAchievementNotification(
        userId,
        newAchievement,
      );
    } catch (error) {
      if (
        error instanceof Prisma.PrismaClientKnownRequestError &&
        error.code === 'P2002'
      ) {
        // Ignore unique constraint violations (user already has badge)
        return;
      }
      this.logger.error(
        `Failed to grant achievement to user ${userId}`,
        getErrorMessage(error),
      );
    }
  }
}
