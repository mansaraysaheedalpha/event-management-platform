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
  cors: { origin: '*', credentials: true },
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
   * Fetches the latest leaderboard data and broadcasts it to the session room.
   * This is a public method called by the GamificationService.
   */
  public async broadcastLeaderboardUpdate(sessionId: string) {
    try {
      // We don't need a specific user ID here, as we're just getting the top 10.
      const leaderboardData =
        await this.gamificationService.getLeaderboard(sessionId);

      const publicRoom = `session:${sessionId}`;
      const eventName = 'leaderboard.updated';

      this.server.to(publicRoom).emit(eventName, leaderboardData);
      this.logger.log(`Broadcasted leaderboard update to room ${publicRoom}`);
    } catch (error) {
      this.logger.error(
        `Failed to broadcast leaderboard update for session ${sessionId}`,
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
}
