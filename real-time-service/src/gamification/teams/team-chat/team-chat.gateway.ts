// src/gamification/teams/team-chat/team-chat.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Logger } from '@nestjs/common';
import { Server } from 'socket.io';
import { TeamChatService } from './team-chat.service';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { ReactTeamMessageDto } from './dto/react-team-message.dto';
import { TeamChatHistoryDto } from './dto/team-chat-history.dto';
import { IsNotEmpty, IsOptional, IsString, MaxLength } from 'class-validator';
import { GamificationService } from '../../gamification.service';
import { PrismaService } from 'src/prisma.service';

// Inline DTO for sending team messages
class SendTeamMessageDto {
  @IsNotEmpty()
  @IsString()
  teamId: string;

  @IsString()
  @IsNotEmpty()
  @MaxLength(2000)
  text: string;

  @IsNotEmpty()
  @IsString()
  idempotencyKey: string;

  @IsOptional()
  metadata?: Record<string, any>;
}

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class TeamChatGateway {
  private readonly logger = new Logger(TeamChatGateway.name);

  @WebSocketServer()
  server: Server;

  constructor(
    private readonly teamChatService: TeamChatService,
    private readonly gamificationService: GamificationService,
    private readonly prisma: PrismaService,
  ) {}

  // ─── Send Message ─────────────────────────────────────────────

  @SubscribeMessage('team.chat.send')
  async handleSendMessage(
    @ConnectedSocket() client: AuthenticatedSocket,
    @MessageBody() dto: SendTeamMessageDto,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      // Verify team membership
      await this.teamChatService.assertTeamMembership(user.sub, dto.teamId);

      // Ensure the client socket is in the team room (belt-and-suspenders:
      // session.join auto-joins but is fire-and-forget; this guarantees it)
      await client.join(`team:${dto.teamId}`);

      // Get the session ID for points (team belongs to session)
      const team = await this._getTeam(dto.teamId);

      // Send the message
      const message = await this.teamChatService.sendMessage(
        user.sub,
        dto.teamId,
        dto.text,
        dto.idempotencyKey,
        dto.metadata,
      );

      // Award points for team chat participation
      void this.gamificationService
        .awardPoints(user.sub, team.sessionId, 'MESSAGE_SENT')
        .catch((err) =>
          this.logger.warn(`Failed to award MESSAGE_SENT points: ${err}`),
        );

      // Broadcast to team room (all sockets in the room, including sender)
      this.server.to(`team:${dto.teamId}`).emit('team.chat.message.new', {
        message,
      });

      return {
        event: 'team.chat.send.response',
        data: { success: true, message },
      };
    } catch (error: any) {
      this.logger.error(
        `Failed to send team message: ${error?.message || error}`,
      );
      return {
        event: 'team.chat.send.response',
        data: { success: false, error: error?.message || 'Unknown error' },
      };
    }
  }

  // ─── React to Message ─────────────────────────────────────────

  @SubscribeMessage('team.chat.react')
  async handleReactToMessage(
    @ConnectedSocket() client: AuthenticatedSocket,
    @MessageBody() dto: ReactTeamMessageDto,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      // Verify team membership
      await this.teamChatService.assertTeamMembership(user.sub, dto.teamId);

      // Toggle the reaction
      const updatedMessage = await this.teamChatService.toggleReaction(
        user.sub,
        dto.teamId,
        dto.messageId,
        dto.emoji,
        dto.idempotencyKey,
      );

      // Broadcast update to team room
      this.server.to(`team:${dto.teamId}`).emit('team.chat.message.updated', {
        message: updatedMessage,
      });

      return {
        event: 'team.chat.react.response',
        data: { success: true, message: updatedMessage },
      };
    } catch (error: any) {
      this.logger.error(
        `Failed to react to team message: ${error?.message || error}`,
      );
      return {
        event: 'team.chat.react.response',
        data: { success: false, error: error?.message || 'Unknown error' },
      };
    }
  }

  // ─── Get Chat History ─────────────────────────────────────────

  @SubscribeMessage('team.chat.history')
  async handleGetHistory(
    @ConnectedSocket() client: AuthenticatedSocket,
    @MessageBody() dto: TeamChatHistoryDto,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      // Verify team membership
      await this.teamChatService.assertTeamMembership(user.sub, dto.teamId);

      // Ensure the client socket is in the team room so it receives broadcasts
      await client.join(`team:${dto.teamId}`);

      // Fetch history
      const messages = await this.teamChatService.getHistory(
        dto.teamId,
        dto.limit ?? 50,
        dto.before,
      );

      return {
        event: 'team.chat.history.response',
        data: {
          success: true,
          messages,
          hasMore: messages.length === (dto.limit ?? 50),
        },
      };
    } catch (error: any) {
      this.logger.error(
        `Failed to fetch team chat history: ${error?.message || error}`,
      );
      return {
        event: 'team.chat.history.response',
        data: { success: false, error: error?.message || 'Unknown error' },
      };
    }
  }

  // ─── Helpers ──────────────────────────────────────────────────

  private async _getTeam(teamId: string) {
    const team = await this.prisma.team.findUnique({
      where: { id: teamId },
      select: { sessionId: true },
    });
    if (!team) {
      throw new Error(`Team ${teamId} not found`);
    }
    return team;
  }
}
