//src/comm/dm/dm.gateway.ts
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
import { DmService } from './dm.service';
import { SendDmDto } from './dto/send-dm.dto';
import { ReadReceiptDto } from './dto/read-receipt.dto';
import { DeliveryReceiptDto } from './dto/delivery-receipt.dto';
import { EditDmDto } from './dto/edit-dm.dto';
import { PrismaService } from 'src/prisma.service';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { DeleteDmDto } from './dto/delete-dm.dto';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class DmGateway {
  private readonly logger = new Logger(DmGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    private readonly dmService: DmService,
    private readonly prisma: PrismaService,
  ) {}

  /**
   * Handles incoming direct message sending requests.
   * Sends the message to both sender's and recipient's private rooms.
   * @param dto - Data transfer object containing DM details.
   * @param client - The connected authenticated socket client.
   * @returns An object indicating success and the new message's ID and timestamp.
   */
  @SubscribeMessage('dm.send')
  async handleSendMessage(
    @MessageBody() dto: SendDmDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const sender = getAuthenticatedUser(client);
    try {
      const newMessage = await this.dmService.sendMessage(sender.sub, dto);

      // --- WORLD-CLASS TARGETED BROADCASTING ---
      // Each user is in their own private room: `user:<userId>`
      const senderRoom = `user:${sender.sub}`;
      const recipientRoom = `user:${dto.recipientId}`;

      const eventName = 'dm.new';

      // Emit to the recipient's room (all of their connected devices)
      this.server.to(recipientRoom).emit(eventName, newMessage);

      // Also emit to the sender's room so their other devices get the sent message
      this.server.to(senderRoom).emit(eventName, newMessage);

      this.logger.log(
        `DM from ${sender.sub} to ${dto.recipientId} broadcasted successfully.`,
      );

      return {
        success: true,
        messageId: newMessage.id,
        timestamp: newMessage.timestamp,
      };
    } catch (error) {
      this.logger.error(
        `Failed to send DM for user ${sender.sub}:`,
        (error as Error).message,
      );
      return { success: false, error: (error as Error).message };
    }
  }

  /**
   * Handles delivery receipt notifications from the message recipient.
   * Updates delivery status and notifies the original sender.
   * @param dto - Delivery receipt details including messageId.
   * @param client - The connected authenticated socket client (recipient).
   * @returns An object indicating success or failure reason.
   */
  @SubscribeMessage('dm.delivered')
  async handleDeliveryReceipt(
    @MessageBody() dto: DeliveryReceiptDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    // The user connected on this socket is the recipient.
    const recipient = getAuthenticatedUser(client);

    const updatedMessage = await this.dmService.markAsDelivered(
      recipient.sub,
      dto,
    );

    // If the service returns null, it means no update was needed, so we stop.
    if (!updatedMessage) {
      return { success: false, reason: 'No update needed or not found.' };
    }

    // --- NOTIFY THE ORIGINAL SENDER ---
    const senderRoom = `user:${updatedMessage.senderId}`;
    const eventName = 'dm.delivery_update';
    // The payload only needs to contain the info that changed.
    const payload = {
      messageId: updatedMessage.id,
      conversationId: updatedMessage.conversationId,
      isDelivered: updatedMessage.isDelivered,
      deliveredAt: updatedMessage.deliveredAt,
    };

    this.server.to(senderRoom).emit(eventName, payload);
    this.logger.log(
      `Sent delivery update for message ${dto.messageId} to user ${updatedMessage.senderId}`,
    );

    // Acknowledge the receipt from the recipient's client.
    return { success: true };
  }

  /**
   * Handles read receipt notifications when the recipient reads the message.
   * Updates read status and notifies the original sender.
   * @param dto - Read receipt details including messageId.
   * @param client - The connected authenticated socket client (reader).
   * @returns An object indicating success or failure reason.
   */
  @SubscribeMessage('dm.read')
  async handleReadReceipt(
    @MessageBody() dto: ReadReceiptDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    // The user on this socket is the one who has read the message.
    const reader = getAuthenticatedUser(client);

    const updatedMessage = await this.dmService.markAsRead(reader.sub, dto);

    if (!updatedMessage) {
      return { success: false, reason: 'No update needed or not found.' };
    }

    // --- NOTIFY THE ORIGINAL SENDER ---
    const senderRoom = `user:${updatedMessage.senderId}`;
    const eventName = 'dm.read_update';

    // The payload only needs the fields that have changed.
    const payload = {
      messageId: updatedMessage.id,
      conversationId: updatedMessage.conversationId,
      isRead: updatedMessage.isRead,
      readAt: updatedMessage.readAt,
    };

    this.server.to(senderRoom).emit(eventName, payload);
    this.logger.log(
      `Sent read update for message ${dto.messageId} to user ${updatedMessage.senderId}`,
    );

    // Acknowledge the receipt from the reader's client.
    return { success: true };
  }

  // **FIXED METHOD**
  @SubscribeMessage('dm.message.edit')
  async handleEditMessage(
    @MessageBody() dto: EditDmDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    try {
      // Destructure the new, richer result from our improved service
      const { updatedMessage, participantIds } =
        await this.dmService.editMessage(user.sub, dto);

      // No more database calls from the gateway! We use the IDs from the service.
      if (participantIds) {
        for (const participantId of participantIds) {
          this.server
            .to(`user:${participantId}`)
            .emit('dm.message.updated', updatedMessage);
        }
      }

      // Use the correct nested object for the response
      return { success: true, messageId: updatedMessage.id };
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(
        `Failed to edit message for user ${user.sub}:`,
        errorMessage,
      );
      return { success: false, error: errorMessage };
    }
  }

  @SubscribeMessage('dm.message.delete')
  async handleDeleteMessage(
    @MessageBody() dto: DeleteDmDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    try {
      const { deletedMessageId, conversation } =
        await this.dmService.deleteMessage(user.sub, dto);

      for (const participant of conversation.participants) {
        this.server
          .to(`user:${participant.userId}`)
          .emit('dm.message.deleted', { messageId: deletedMessageId });
      }

      return { success: true, deletedMessageId };
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(
        `Failed to delete message for user ${user.sub}:`,
        errorMessage,
      );
      return { success: false, error: errorMessage };
    }
  }
}
