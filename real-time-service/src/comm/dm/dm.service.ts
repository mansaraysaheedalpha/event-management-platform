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
