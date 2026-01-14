//src/ops/backchannel/backchannel.gateway.ts
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
import { BackchannelService } from './backchannel.service';
import { SendBackchannelMessageDto } from './dto/send-backchannel-message.dto';
import { BackchannelRoleService } from './backchannel-role.service';

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class BackchannelGateway {
  private readonly logger = new Logger(BackchannelGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    private readonly backchannelService: BackchannelService,
    private readonly backchannelRoleService: BackchannelRoleService,
  ) {}

  /**
   * Handles an authorized staff member joining the backchannel for a session.
   *
   * The user is joined to:
   * 1. General backchannel room (for "All Staff" messages)
   * 2. Role-specific rooms based on their permissions and session assignment:
   *    - STAFF: Organization admins/owners with backchannel permission
   *    - MODERATOR: Users with moderation permissions (qna:moderate, chat:moderate)
   *    - SPEAKER: Users assigned as speakers for this session
   *
   * A user can belong to multiple roles simultaneously.
   */
  @SubscribeMessage('backchannel.join')
  async handleJoinBackchannel(@ConnectedSocket() client: AuthenticatedSocket) {
    try {
      const user = getAuthenticatedUser(client);
      const { sessionId } = client.handshake.query as { sessionId: string };
      const requiredPermission = 'backchannel:join';

      this.logger.log(
        `Backchannel join attempt - User: ${user?.sub}, SessionId: ${sessionId}, Permissions: ${user?.permissions?.join(', ')}`,
      );

      if (!user.permissions?.includes(requiredPermission)) {
        this.logger.warn(
          `User ${user.sub} attempted to join backchannel without permission`,
        );
        return {
          success: false,
          error: {
            message: 'You do not have permission to join the backchannel.',
            statusCode: 403,
          },
        };
      }

      // Determine user's backchannel roles based on permissions and session assignment
      const userRoles = await this.backchannelRoleService.getUserBackchannelRoles(
        user.sub,
        sessionId,
        user.permissions || [],
      );

      // Build list of rooms to join
      const backchannelRoom = `backchannel:${sessionId}`;
      const roleRooms = this.backchannelRoleService.getRoomNamesForRoles(
        sessionId,
        userRoles,
      );

      // Join general backchannel room and all applicable role-specific rooms
      const allRooms = [backchannelRoom, ...roleRooms];
      await client.join(allRooms);

      this.logger.log(
        `Staff member ${user.sub} joined backchannel for session ${sessionId} with roles: [${userRoles.join(', ')}]`,
      );

      // Fetch and emit message history to the joining client
      try {
        const messages = await this.backchannelService.getHistory(sessionId);
        client.emit('backchannel.history', { messages });
      } catch (historyError) {
        this.logger.error(
          `Failed to fetch backchannel history for session ${sessionId}`,
          getErrorMessage(historyError),
        );
        // Don't fail the join, just log the error - client will still be in the room
      }

      // Return success with the user's roles for frontend awareness
      return { success: true, roles: userRoles };
    } catch (error) {
      this.logger.error(
        `Failed to handle backchannel join: ${getErrorMessage(error)}`,
      );
      return {
        success: false,
        error: {
          message: 'Failed to join backchannel. Please try again.',
          statusCode: 500,
        },
      };
    }
  }

  /**
   * Handles a new message sent to the backchannel.
   * Can be a general message or a targeted "whisper".
   */
  @SubscribeMessage('backchannel.message.send')
  async handleSendMessage(
    @MessageBody() dto: SendBackchannelMessageDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };
    const requiredPermission = 'backchannel:send';

    if (!user.permissions?.includes(requiredPermission)) {
      this.logger.warn(
        `User ${user.sub} attempted to send backchannel message without permission`,
      );
      return {
        success: false,
        error: {
          message: 'You do not have permission to send backchannel messages.',
          statusCode: 403,
        },
      };
    }

    try {
      const newMessage = await this.backchannelService.sendMessage(
        user.sub,
        sessionId,
        dto,
      );

      const backchannelRoom = `backchannel:${sessionId}`;
      const eventName = 'backchannel.message.new';

      if (dto.targetUserId) {
        // Whisper to a specific user.
        // Send to the sender's socket ID and the target's private user room.
        this.server
          .to(client.id)
          .to(`user:${dto.targetUserId}`)
          .emit(eventName, {
            ...newMessage,
            isWhisper: true,
          });
        this.logger.log(`Sent whisper from ${user.sub} to ${dto.targetUserId}`);
      } else if (dto.targetRole) {
        // Whisper to a specific role.
        const roleSpecificRoom = `backchannel:${sessionId}:role:${dto.targetRole}`;

        // Send to the role-specific room AND to the original sender.
        this.server
          .to(roleSpecificRoom)
          .to(client.id)
          .emit(eventName, {
            ...newMessage,
            isWhisper: true,
            whisperTarget: `Role: ${dto.targetRole}`,
          });
        this.logger.log(
          `Sent whisper from ${user.sub} to role ${dto.targetRole}`,
        );
      } else {
        // This is a regular message to the whole backchannel.
        this.server.to(backchannelRoom).emit(eventName, newMessage);
      }

      return { success: true, messageId: newMessage.id };
    } catch (error) {
      this.logger.error(
        `Failed to send backchannel message for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }
}
