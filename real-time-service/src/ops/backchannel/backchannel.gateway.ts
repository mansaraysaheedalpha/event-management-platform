//src/ops/backchannel/backchannel.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { ForbiddenException, Logger } from '@nestjs/common';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { BackchannelService } from './backchannel.service';
import { SendBackchannelMessageDto } from './dto/send-backchannel-message.dto';

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class BackchannelGateway {
  private readonly logger = new Logger(BackchannelGateway.name);
  @WebSocketServer() server: Server;

  constructor(private readonly backchannelService: BackchannelService) {}

  /**
   * Handles an authorized staff member joining the backchannel for a session.
   * Fetches and emits message history after successful join.
   */
  @SubscribeMessage('backchannel.join')
  async handleJoinBackchannel(@ConnectedSocket() client: AuthenticatedSocket) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };
    const requiredPermission = 'backchannel:join';

    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to join the backchannel.',
      );
    }

    const backchannelRoom = `backchannel:${sessionId}`;
    const roleSpecificRoom = `backchannel:${sessionId}:role:${user.role}`;

    // Join both the general backchannel and the user's role-specific room
    await client.join([backchannelRoom, roleSpecificRoom]);

    this.logger.log(
      `Staff member ${user.sub} (${user.role}) joined backchannel for session ${sessionId}`,
    );

    // Fetch and emit message history to the joining client
    try {
      const messages = await this.backchannelService.getHistory(sessionId);
      client.emit('backchannel.history', { messages });
    } catch (error) {
      this.logger.error(
        `Failed to fetch backchannel history for session ${sessionId}`,
        getErrorMessage(error),
      );
      // Don't fail the join, just log the error - client will still be in the room
    }

    return { success: true };
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
      throw new ForbiddenException(
        'You do not have permission to send backchannel messages.',
      );
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
