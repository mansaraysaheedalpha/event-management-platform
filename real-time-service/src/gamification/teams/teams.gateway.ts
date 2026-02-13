//src/gamification/teams/teams.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  OnGatewayInit,
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
import { GamificationService } from '../gamification.service';
import { TeamNotificationsService } from './notifications/team-notifications.service';

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class TeamsGateway implements OnGatewayInit {
  private readonly logger = new Logger(TeamsGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    private readonly teamsService: TeamsService,
    private readonly gamificationService: GamificationService,
    private readonly teamNotificationsService: TeamNotificationsService,
  ) {}

  afterInit(server: Server) {
    this.teamNotificationsService.setServer(server);
  }

  /**
   * Returns all existing teams for the session when a client connects or requests the list.
   */
  @SubscribeMessage('teams.list')
  async handleListTeams(@ConnectedSocket() client: AuthenticatedSocket) {
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const teams = await this.teamsService.getSessionTeams(sessionId);
      return { event: 'teams.list.response', data: { success: true, teams } };
    } catch (error) {
      this.logger.error(
        `Failed to list teams for session ${sessionId}`,
        getErrorMessage(error),
      );
      return { event: 'teams.list.response', data: { success: false, teams: [] } };
    }
  }

  /**
   * Handles a user's request to create a new team in a session.
   * Joins the creator to the team room and broadcasts to session.
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

      // Broadcast the new team to everyone in the session
      if (newTeam) {
        this.server.to(publicRoom).emit('team.created', newTeam);
        this.logger.log(
          `Broadcasted new team ${newTeam.id} to room ${publicRoom}`,
        );

        // Join the creator to the team room for private team notifications
        const teamRoom = `team:${newTeam.id}`;
        await client.join(teamRoom);
        this.logger.log(`User ${user.sub} joined team room: ${teamRoom}`);
      }

      // Award gamification points for creating a team
      void this.gamificationService
        .awardPoints(user.sub, sessionId, 'TEAM_CREATED')
        .catch((err) =>
          this.logger.warn(`Failed to award TEAM_CREATED points: ${getErrorMessage(err)}`),
        );

      return { event: 'team.create.response', data: { success: true, team: newTeam } };
    } catch (error) {
      this.logger.error(
        `Failed to create team for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { event: 'team.create.response', data: { success: false, error: getErrorMessage(error) } };
    }
  }

  /**
   * Handles a user's request to join a team.
   * Joins client to team room, notifies team, broadcasts roster update.
   */
  @SubscribeMessage('team.join')
  async handleJoinTeam(
    @MessageBody() dto: JoinTeamDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const updatedTeam = await this.teamsService.joinTeam(user.sub, dto);
      this.server
        .to(`session:${sessionId}`)
        .emit('team.roster.updated', updatedTeam);

      // Join the user to the team room
      const teamRoom = `team:${dto.teamId}`;
      await client.join(teamRoom);
      this.logger.log(`User ${user.sub} joined team room: ${teamRoom}`);

      // Notify existing team members about the new joiner
      const memberInfo = updatedTeam?.members?.find(
        (m: any) => m.userId === user.sub,
      );
      this.teamNotificationsService.notifyMemberJoined(dto.teamId, {
        userId: user.sub,
        firstName: memberInfo?.user?.firstName ?? undefined,
        lastName: memberInfo?.user?.lastName ?? undefined,
      });

      // Award gamification points for joining a team
      void this.gamificationService
        .awardPoints(user.sub, sessionId, 'TEAM_JOINED')
        .catch((err) =>
          this.logger.warn(`Failed to award TEAM_JOINED points: ${getErrorMessage(err)}`),
        );

      return { event: 'team.join.response', data: { success: true, teamId: dto.teamId } };
    } catch (error) {
      this.logger.error(
        `Failed to join team for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { event: 'team.join.response', data: { success: false, error: getErrorMessage(error) } };
    }
  }

  /**
   * Handles a user's request to leave a team.
   * Removes client from team room, notifies team, broadcasts roster update.
   */
  @SubscribeMessage('team.leave')
  async handleLeaveTeam(
    @MessageBody() dto: LeaveTeamDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      // Notify team members before the user leaves
      this.teamNotificationsService.notifyMemberLeft(dto.teamId, {
        userId: user.sub,
      });

      const updatedTeam = await this.teamsService.leaveTeam(user.sub, dto);
      this.server
        .to(`session:${sessionId}`)
        .emit('team.roster.updated', updatedTeam);

      // Leave the team room
      const teamRoom = `team:${dto.teamId}`;
      await client.leave(teamRoom);
      this.logger.log(`User ${user.sub} left team room: ${teamRoom}`);

      return { event: 'team.leave.response', data: { success: true, teamId: dto.teamId } };
    } catch (error) {
      this.logger.error(
        `Failed to leave team for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { event: 'team.leave.response', data: { success: false, error: getErrorMessage(error) } };
    }
  }
}
