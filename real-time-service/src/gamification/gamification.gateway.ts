//src/gamification/gamification.gateway.ts
import {
  ConnectedSocket,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { forwardRef, Inject, Logger, OnModuleDestroy } from '@nestjs/common';
import { GamificationService } from './gamification.service';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { TeamNotificationsService } from './teams/notifications/team-notifications.service';

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class GamificationGateway implements OnModuleDestroy {
  private readonly logger = new Logger(GamificationGateway.name);
  @WebSocketServer() server: Server;

  // Per-session debounce timers to prevent leaderboard query flooding
  private leaderboardDebounceTimers = new Map<string, NodeJS.Timeout>();
  private static readonly LEADERBOARD_DEBOUNCE_MS = 3000;

  // Track previous team ranks per session for rank-change detection
  private previousTeamRanks = new Map<string, Map<string, number>>();

  constructor(
    @Inject(forwardRef(() => GamificationService))
    private readonly gamificationService: GamificationService,
    private readonly teamNotificationsService: TeamNotificationsService,
  ) {}

  /**
   * Handles a client's request to fetch the current leaderboard for a session.
   */
  @SubscribeMessage('leaderboard.request')
  async handleRequestLeaderboard(
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const leaderboardData = await this.gamificationService.getLeaderboard(
        sessionId,
        user.sub,
      );

      return {
        success: true,
        event: 'leaderboard.data',
        data: leaderboardData,
      };
    } catch (error) {
      this.logger.error(
        `Failed to fetch leaderboard for user ${user.sub} in session ${sessionId}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Handles a client's request to fetch their unlocked achievements and progress.
   */
  @SubscribeMessage('achievements.request')
  async handleRequestAchievements(
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const [achievements, progress] = await Promise.all([
        this.gamificationService.getUserAchievements(user.sub),
        this.gamificationService.getAchievementProgress(user.sub, sessionId),
      ]);

      return {
        success: true,
        event: 'achievements.data',
        data: { achievements, progress },
      };
    } catch (error) {
      this.logger.error(
        `Failed to fetch achievements for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Handles a client's request to fetch their gamification stats.
   */
  @SubscribeMessage('user.stats.request')
  async handleRequestUserStats(
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const stats = await this.gamificationService.getUserStats(
        user.sub,
        sessionId,
      );

      return {
        success: true,
        event: 'user.stats.data',
        data: stats,
      };
    } catch (error) {
      this.logger.error(
        `Failed to fetch user stats for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Debounced leaderboard broadcast. Coalesces rapid-fire calls (e.g. from
   * many concurrent awardPoints) into a single DB query per session.
   */
  public broadcastLeaderboardUpdate(sessionId: string) {
    const existing = this.leaderboardDebounceTimers.get(sessionId);
    if (existing) clearTimeout(existing);

    const timer = setTimeout(() => {
      this.leaderboardDebounceTimers.delete(sessionId);
      this._doBroadcastLeaderboardUpdate(sessionId);
    }, GamificationGateway.LEADERBOARD_DEBOUNCE_MS);

    this.leaderboardDebounceTimers.set(sessionId, timer);
  }

  private async _doBroadcastLeaderboardUpdate(sessionId: string) {
    try {
      const [individualLeaderboard, teamLeaderboard] = await Promise.all([
        this.gamificationService.getLeaderboard(sessionId),
        this.gamificationService.getTeamLeaderboard(sessionId),
      ]);

      const publicRoom = `session:${sessionId}`;

      this.server.to(publicRoom).emit('leaderboard.updated', {
        topEntries: individualLeaderboard.topEntries,
      });

      this.server.to(publicRoom).emit('team.leaderboard.updated', {
        teamScores: teamLeaderboard,
      });

      // Detect rank changes and notify teams
      this._detectAndNotifyRankChanges(sessionId, teamLeaderboard);

      this.logger.log(`Broadcasted leaderboard updates to room ${publicRoom}`);
    } catch (error) {
      this.logger.error(
        `Failed to broadcast leaderboard updates for session ${sessionId}`,
        getErrorMessage(error),
      );
    }
  }

  /**
   * Compares current team ranks against previous snapshot and sends
   * notifications to teams whose rank changed.
   */
  private _detectAndNotifyRankChanges(
    sessionId: string,
    teamLeaderboard: Array<{
      teamId: string;
      name: string;
      rank: number;
      score: number;
      memberCount: number;
    }>,
  ) {
    const prevRanks = this.previousTeamRanks.get(sessionId);
    const currentRanks = new Map<string, number>();

    for (const entry of teamLeaderboard) {
      currentRanks.set(entry.teamId, entry.rank);

      if (prevRanks) {
        const previousRank = prevRanks.get(entry.teamId);
        if (previousRank !== undefined && previousRank !== entry.rank) {
          this.teamNotificationsService.notifyRankChanged(entry.teamId, {
            previousRank,
            newRank: entry.rank,
            teamName: entry.name,
          });
        }
      }
    }

    this.previousTeamRanks.set(sessionId, currentRanks);
  }

  /**
   * Sends a private notification to a user when they unlock an achievement.
   */
  public sendAchievementNotification(targetUserId: string, achievement: any) {
    const userRoom = `user:${targetUserId}`;
    this.server.to(userRoom).emit('achievement.unlocked', achievement);
    this.logger.log(
      `Sent achievement notification '${achievement.badgeName}' to user ${targetUserId}`,
    );
  }

  /**
   * Sends a private notification to a user when they are awarded points.
   */
  public sendPointsAwardedNotification(targetUserId: string, payload: any) {
    const userRoom = `user:${targetUserId}`;
    this.server.to(userRoom).emit('gamification.points.awarded', payload);
  }

  /**
   * Sends a private notification to a user about their streak status change.
   */
  public sendStreakNotification(
    targetUserId: string,
    payload: { count: number; multiplier: number; active: boolean },
  ) {
    const userRoom = `user:${targetUserId}`;
    this.server.to(userRoom).emit('gamification.streak.updated', payload);
    this.logger.log(
      `Sent streak notification to user ${targetUserId}: ${payload.count}x (${payload.multiplier}x multiplier)`,
    );
  }

  onModuleDestroy() {
    this.leaderboardDebounceTimers.forEach((timer) => clearTimeout(timer));
    this.leaderboardDebounceTimers.clear();
    this.previousTeamRanks.clear();
  }
}
