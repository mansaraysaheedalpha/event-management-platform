//src/comm/chat/chat.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { HttpException, Logger } from '@nestjs/common';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { ChatService } from './chat.service';
import { SendMessageDto } from './dto/send-message.dto';
import { EditMessageDto } from './dto/edit-message.dto';
import { DeleteMessageDto } from './dto/delete-message.dto';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { ReactToMessageDto } from './dto/react-to-message.dto';
import { Throttle } from '@nestjs/throttler';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class ChatGateway {
  private readonly logger = new Logger(ChatGateway.name);
  @WebSocketServer() server: Server;

  constructor(private readonly chatService: ChatService) {}

  /**
   * Handles incoming 'chat.message.send' events.
   * Sends a message to the specified session and broadcasts it to all participants.
   *
   * @param dto - The message payload sent by the client.
   * @param client - The connected WebSocket client (with authentication).
   * @returns An object containing success status and message ID or error.
   */
  @Throttle({
    default: { limit: 100, ttl: 60000 },
    vip: { limit: 500, ttl: 60000 },
  }) // Apply specific limits for this action
  @SubscribeMessage('chat.message.send')
  async handleSendMessage(
    @MessageBody() dto: SendMessageDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const newMessage = (await this.chatService.sendMessage(
        user.sub,
        sessionId,
        dto,
      )) as { id: string }; // Ensure the expected type is asserted
      const publicRoom = `session:${sessionId}`;
      this.server.to(publicRoom).emit('chat.message.new', newMessage);
      return { success: true, messageId: newMessage.id };
    } catch (error) {
      this.logger.error(
        `Failed to send message for user ${user.sub}:`,
        getErrorMessage(error),
      );
      if (error instanceof HttpException) {
        return {
          success: false,
          error: { message: error.message, statusCode: error.getStatus() },
        };
      }
      return { success: false, error: 'An internal server error occurred.' };
    }
  }

  /**
   * Handles 'chat.message.edit' events.
   * Edits an existing message and emits the updated message to the session.
   *
   * @param dto - The edit payload including messageId and new content.
   * @param client - The authenticated WebSocket client.
   * @returns An object with success status and updated message ID or error.
   */
  @SubscribeMessage('chat.message.edit')
  async handleEditMessage(
    @MessageBody() dto: EditMessageDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const editedMessage = (await this.chatService.editMessage(
        user.sub,
        dto,
      )) as { id: string };
      const publicRoom = `session:${sessionId}`;
      this.server.to(publicRoom).emit('chat.message.updated', editedMessage);
      return { success: true, messageId: editedMessage.id };
    } catch (error) {
      this.logger.error(
        `Failed to edit message for user ${user.sub}:`,
        getErrorMessage(error),
      );
      if (error instanceof HttpException) {
        return {
          success: false,
          error: { message: error.message, statusCode: error.getStatus() },
        };
      }
      return { success: false, error: 'An internal server error occurred.' };
    }
  }

  /**
   * Handles 'chat.message.delete' events.
   * Deletes a message (based on user permissions) and notifies the session participants.
   *
   * @param dto - Payload containing the messageId to be deleted.
   * @param client - The authenticated client attempting deletion.
   * @returns An object with deletion status and deleted message ID or error.
   */
  @SubscribeMessage('chat.message.delete')
  async handleDeleteMessage(
    @MessageBody() dto: DeleteMessageDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      // The service handles the complex permission logic
      const deleteResult = await this.chatService.deleteMessage(
        user.sub,
        dto,
        user.permissions,
      );

      const publicRoom = `session:${deleteResult.sessionId}`;
      const payload = { messageId: deleteResult.deletedMessageId };
      this.server.to(publicRoom).emit('chat.message.deleted', payload);

      return { success: true, deletedMessageId: deleteResult.deletedMessageId };
    } catch (error) {
      this.logger.error(
        `Failed to delete message for user ${user.sub}:`,
        getErrorMessage(error),
      );
      if (error instanceof HttpException) {
        return {
          success: false,
          error: { message: error.message, statusCode: error.getStatus() },
        };
      }
      return { success: false, error: 'An internal server error occurred.' };
    }
  }

  /**
   * Handles a user reacting to a specific message.
   */
  @SubscribeMessage('chat.message.react')
  async handleReactToMessage(
    @MessageBody() dto: ReactToMessageDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const updatedMessageWithReactions: {
        id: string;
        [key: string]: any;
      } | null = await this.chatService.reactToMessage(user.sub, dto);

      if (updatedMessageWithReactions) {
        const publicRoom = `session:${sessionId}`;
        const eventName = 'chat.message.updated';

        // Broadcast the fully updated message with the new reaction summary
        this.server.to(publicRoom).emit(eventName, updatedMessageWithReactions);
        this.logger.log(
          `Broadcasted reaction update for message ${dto.messageId} to room ${publicRoom}`,
        );
      }

      return { success: true, messageId: dto.messageId };
    } catch (error) {
      this.logger.error(
        `Failed to process reaction for user ${user.sub}:`,
        getErrorMessage(error),
      );
      if (error instanceof HttpException) {
        return {
          success: false,
          error: { message: error.message, statusCode: error.getStatus() },
        };
      }
      return { success: false, error: 'An internal server error occurred.' };
    }
  }
}
