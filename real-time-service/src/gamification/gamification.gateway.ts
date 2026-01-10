//src/gamification/gamification.gateway.ts
import {
  ConnectedSocket,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { forwardRef, Inject, Logger } from '@nestjs/common';
import { GamificationService } from './gamification.service';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { GamificationAchievement } from '@prisma/client';

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class GamificationGateway {
  private readonly logger = new Logger(GamificationGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    @Inject(forwardRef(() => GamificationService))
    private readonly gamificationService: GamificationService,
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

      // Respond directly to the client that made the request.
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
   * Fetches the latest individual and team leaderboards and broadcasts them.
   */
  public async broadcastLeaderboardUpdate(sessionId: string) {
    try {
      // Fetch both leaderboards simultaneously
      const [individualLeaderboard, teamLeaderboard] = await Promise.all([
        this.gamificationService.getLeaderboard(sessionId),
        this.gamificationService.getTeamLeaderboard(sessionId),
      ]);

      const publicRoom = `session:${sessionId}`;

      // Broadcast individual leaderboard
      this.server.to(publicRoom).emit('leaderboard.updated', {
        topEntries: individualLeaderboard.topEntries,
      });

      // Broadcast team leaderboard
      this.server.to(publicRoom).emit('team.leaderboard.updated', {
        teamScores: teamLeaderboard,
      });

      this.logger.log(`Broadcasted leaderboard updates to room ${publicRoom}`);
    } catch (error) {
      this.logger.error(
        `Failed to broadcast leaderboard updates for session ${sessionId}`,
        getErrorMessage(error),
      );
    }
  }

  /**
   * Sends a private notification to a user when they unlock an achievement.
   * This is a public method called by the GamificationService.
   */
  public sendAchievementNotification(
    targetUserId: string,
    achievement: GamificationAchievement,
  ) {
    const userRoom = `user:${targetUserId}`;
    const eventName = 'achievement.unlocked';

    this.server.to(userRoom).emit(eventName, achievement);
    this.logger.log(
      `Sent achievement notification '${achievement.badgeName}' to user ${targetUserId}`,
    );
  }

  /**
   * Sends a private notification to a user when they are awarded points.
   */
  public sendPointsAwardedNotification(targetUserId: string, payload: any) {
    const userRoom = `user:${targetUserId}`;
    const eventName = 'gamification.points.awarded';
    this.server.to(userRoom).emit(eventName, payload);
  }
}