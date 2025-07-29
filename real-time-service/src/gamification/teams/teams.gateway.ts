import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger } from '@nestjs/common';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { TeamsService } from './teams.service';
import { CreateTeamDto } from './dto/create-team.dto';
import { LeaveTeamDto } from './dto/leave-team.dto';
import { JoinTeamDto } from './dto/join-team.dto';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class TeamsGateway {
  private readonly logger = new Logger(TeamsGateway.name);
  @WebSocketServer() server: Server;

  constructor(private readonly teamsService: TeamsService) {}

  /**
   * Handles a user's request to create a new team in a session.
   */
  @SubscribeMessage('team.create')
  async handleCreateTeam(
    @MessageBody() dto: CreateTeamDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const newTeam = await this.teamsService.createTeam(
        user.sub,
        sessionId,
        dto,
      );

      const publicRoom = `session:${sessionId}`;
      const eventName = 'team.created';

      // Broadcast the new team to everyone in the session
      if (newTeam) {
        this.server.to(publicRoom).emit(eventName, newTeam);
        this.logger.log(
          `Broadcasted new team ${newTeam.id} to room ${publicRoom}`,
        );
      } else {
        this.logger.warn(
          `Attempted to broadcast a null team to room ${publicRoom}`,
        );
      }

      return { success: true, team: newTeam };
    } catch (error) {
      this.logger.error(
        `Failed to create team for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Handles a user's request to join a team.
   */
  @SubscribeMessage('team.join')
  async handleJoinTeam(
    @MessageBody() dto: JoinTeamDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const updatedTeam = await this.teamsService.joinTeam(
        user.sub,
        dto.teamId,
      );
      this.server
        .to(`session:${sessionId}`)
        .emit('team.roster.updated', updatedTeam);
      return { success: true, teamId: dto.teamId };
    } catch (error) {
      this.logger.error(
        `Failed to join team for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Handles a user's request to leave a team.
   */
  @SubscribeMessage('team.leave')
  async handleLeaveTeam(
    @MessageBody() dto: LeaveTeamDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const updatedTeam = await this.teamsService.leaveTeam(
        user.sub,
        dto.teamId,
      );
      this.server
        .to(`session:${sessionId}`)
        .emit('team.roster.updated', updatedTeam);
      return { success: true, teamId: dto.teamId };
    } catch (error) {
      this.logger.error(
        `Failed to leave team for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }
}
