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

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class ChatGateway {
  private readonly logger = new Logger(ChatGateway.name);
  @WebSocketServer() server: Server;

  constructor(private readonly chatService: ChatService) {}

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
      this.logger.error(
        `Failed to send message for user ${user.sub}:`,
        (error as Error).message,
      );
      return { success: false, error: (error as Error).message };
    }
  }

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
}
