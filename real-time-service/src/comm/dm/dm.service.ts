import {
  BadRequestException,
  ConflictException,
  Injectable,
  Logger,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { DeliveryReceiptDto } from './dto/delivery-receipt.dto';
import { ReadReceiptDto } from './dto/read-receipt.dto';
import { SendDmDto } from './dto/send-dm.dto';
import { PublisherService } from 'src/shared/services/publisher.service';

@Injectable()
export class DmService {
  private readonly logger = new Logger(DmService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
    private readonly publisherService: PublisherService,
  ) {}

  /**
   * Sends a direct message from the sender to the recipient.
   * Checks idempotency and creates a conversation if none exists.
   * @param senderId - ID of the user sending the message.
   * @param dto - DTO containing recipientId, text, and idempotencyKey.
   * @throws BadRequestException if sender tries to message themselves.
   * @throws ConflictException if duplicate message detected.
   * @returns The created direct message object.
   */
  async sendMessage(senderId: string, dto: SendDmDto) {
    const { recipientId, text, idempotencyKey } = dto;

    if (senderId === recipientId) {
      throw new BadRequestException(
        'You cannot send a direct message to yourself.',
      );
    }

    const canProceed =
      await this.idempotencyService.checkAndSet(idempotencyKey);
    if (!canProceed) {
      throw new ConflictException(
        'Duplicate request. This message has already been sent.',
      );
    }

    const conversation = await this.findOrCreateConversation(
      senderId,
      recipientId,
    );

    this.logger.log(
      `User ${senderId} sending DM to ${recipientId} in conversation ${conversation.id}`,
    );

    const directMessage = await this.prisma.directMessage.create({
      data: {
        text,
        senderId,
        conversationId: conversation.id,
      },
      include: {
        sender: {
          select: { id: true, firstName: true, lastName: true },
        },
      },
    });

    return directMessage;
  }

  /**
   * Marks a direct message as delivered by the recipient.
   * Ensures the recipient is a participant and not the sender.
   * Publishes a sync event on successful update.
   * @param recipientId - ID of the user marking the message delivered.
   * @param dto - DTO containing the messageId.
   * @returns The updated direct message or null if no update was needed.
   */
  async markAsDelivered(recipientId: string, dto: DeliveryReceiptDto) {
    const { messageId } = dto;

    const result = await this.prisma.directMessage.updateMany({
      where: {
        id: messageId,
        isDelivered: false,
        // --- CORRECTED LOGIC ---
        conversation: {
          participants: {
            some: {
              id: recipientId, // Filter by the 'id' field of the related UserReference
            },
          },
        },
        NOT: {
          senderId: recipientId,
        },
      },
      data: {
        isDelivered: true,
        deliveredAt: new Date(),
      },
    });

    if (result.count === 0) {
      this.logger.warn(
        `Delivery receipt for message ${messageId} by user ${recipientId} resulted in no update.`,
      );
      return null;
    }

    this.logger.log(
      `Message ${messageId} marked as delivered by ${recipientId}`,
    );

    const updatedMessage = await this.prisma.directMessage.findUnique({
      where: { id: messageId },
    });

    // --- ADD SYNC EVENT ---
    if (updatedMessage) {
      const syncPayload = {
        resource: 'DIRECT_MESSAGE',
        action: 'UPDATED',
        payload: updatedMessage,
      };
      void this.publisherService.publish('sync-events', syncPayload);
    }

    return updatedMessage;
  }

  /**
   * Marks a direct message as read by the reader.
   * Ensures the reader is a participant and not the sender.
   * Publishes a sync event on successful update.
   * @param readerId - ID of the user marking the message read.
   * @param dto - DTO containing the messageId.
   * @returns The updated direct message or null if no update was needed.
   */
  async markAsRead(readerId: string, dto: ReadReceiptDto) {
    const { messageId } = dto;

    const result = await this.prisma.directMessage.updateMany({
      where: {
        id: messageId,
        isRead: false,
        // --- CORRECTED LOGIC ---
        conversation: {
          participants: {
            some: {
              id: readerId, // Filter by the 'id' field of the related UserReference
            },
          },
        },
        NOT: {
          senderId: readerId,
        },
      },
      data: {
        isRead: true,
        readAt: new Date(),
      },
    });

    if (result.count === 0) {
      this.logger.warn(
        `Read receipt for message ${messageId} by user ${readerId} resulted in no update.`,
      );
      return null;
    }

    this.logger.log(`Message ${messageId} marked as read by ${readerId}`);

    const updatedMessage = await this.prisma.directMessage.findUnique({
      where: { id: messageId },
    });

    // --- ADD SYNC EVENT ---
    if (updatedMessage) {
      const syncPayload = {
        resource: 'DIRECT_MESSAGE',
        action: 'UPDATED',
        payload: updatedMessage,
      };
      void this.publisherService.publish('sync-events', syncPayload);
    }
    return updatedMessage;
  }

  /**
   * Finds an existing conversation between two users or creates a new one.
   * @param userId1 - ID of the first user.
   * @param userId2 - ID of the second user.
   * @returns The found or newly created conversation object.
   */
  private async findOrCreateConversation(userId1: string, userId2: string) {
    let conversation = await this.prisma.conversation.findFirst({
      where: {
        AND: [
          // --- CORRECTED LOGIC ---
          { participants: { some: { id: userId1 } } },
          { participants: { some: { id: userId2 } } },
        ],
      },
    });

    if (!conversation) {
      conversation = await this.prisma.conversation.create({
        data: {
          participants: {
            connect: [{ id: userId1 }, { id: userId2 }],
          },
        },
      });
    }

    return conversation;
  }
}
