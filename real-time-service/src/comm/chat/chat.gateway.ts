import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger } from '@nestjs/common';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { ChatService } from './chat.service';
import { SendMessageDto } from './dto/send-message.dto';
import { EditMessageDto } from './dto/edit-message.dto';
import { DeleteMessageDto } from './dto/delete-message.dto';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { ReactToMessageDto } from './dto/react-to-message.dto';

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
  @SubscribeMessage('chat.message.send')
  async handleSendMessage(
    @MessageBody() dto: SendMessageDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const newMessage = await this.chatService.sendMessage(
        user.sub,
        sessionId,
        dto,
      );
      const publicRoom = `session:${sessionId}`;
      this.server.to(publicRoom).emit('chat.message.new', newMessage);
      return { success: true, messageId: newMessage.id };
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(
        `Failed to send message for user ${user.sub}:`,
        errorMessage,
      );
      return { success: false, error: errorMessage };
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
      const editedMessage = await this.chatService.editMessage(user.sub, dto);
      const publicRoom = `session:${sessionId}`;
      this.server.to(publicRoom).emit('chat.message.updated', editedMessage);
      return { success: true, messageId: editedMessage.id };
    } catch (error) {
      this.logger.error(
        `Failed to edit message for user ${user.sub}:`,
        (error as Error).message,
      );
      return {
        success: false,
        error: (error as Error).message,
      };
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
      const { deletedMessageId, sessionId } =
        await this.chatService.deleteMessage(
          user.sub,
          dto.messageId,
          user.permissions, // Pass user's permissions to the service
        );

      const publicRoom = `session:${sessionId}`;
      const payload = { messageId: deletedMessageId };
      this.server.to(publicRoom).emit('chat.message.deleted', payload);

      return { success: true, deletedMessageId };
    } catch (error) {
      this.logger.error(
        `Failed to delete message for user ${user.sub}:`,
        (error as Error).message,
      );
      return {
        success: false,
        error: (error as Error).message,
      };
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
      const updatedMessageWithReactions = await this.chatService.reactToMessage(
        user.sub,
        dto,
      );

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
      return { success: false, error: getErrorMessage(error) };
    }
  }
}
