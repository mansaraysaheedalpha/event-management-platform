//src/comm/dm/dm.service.ts
import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { ConfigService } from '@nestjs/config';
import { DeliveryReceiptDto } from './dto/delivery-receipt.dto';
import { ReadReceiptDto } from './dto/read-receipt.dto';
import { SendDmDto } from './dto/send-dm.dto';
import { PublisherService } from 'src/shared/services/publisher.service';
import { DeleteDmDto } from './dto/delete-dm.dto';
import { EditDmDto } from './dto/edit-dm.dto';
import { Prisma } from '@prisma/client';

const directMessageWithSenderPayload =
  Prisma.validator<Prisma.DirectMessageDefaultArgs>()({
    include: {
      sender: { select: { id: true, firstName: true, lastName: true } },
    },
  });

type DirectMessageWithSender = Prisma.DirectMessageGetPayload<
  typeof directMessageWithSenderPayload
>;

type EditDmResult = {
  updatedMessage: DirectMessageWithSender; // Use the strong type instead of 'any'
  participantIds: string[];
};
// Define a strong return type for the delete operation
type DeleteDmResult = {
  deletedMessageId: string;
  conversation: {
    participants: { userId: string }[];
  };
};

@Injectable()
export class DmService {
  private readonly logger = new Logger(DmService.name);
  private readonly EDIT_WINDOW_SECONDS: number;

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
    private readonly publisherService: PublisherService,
    private readonly configService: ConfigService,
  ) {
    this.EDIT_WINDOW_SECONDS = this.configService.get<number>(
      'CHAT_EDIT_WINDOW_SECONDS',
      300,
    );
  }

  /**
   * Sends a direct message from the sender to the recipient.
   * Checks idempotency and creates a conversation if none exists.
   * @param senderId - ID of the user sending the message.
   * @param senderEmail - Email of the sender.
   * @param senderName - Name of the sender.
   * @param dto - DTO containing recipientId, text, and idempotencyKey.
   * @throws BadRequestException if sender tries to message themselves.
   * @throws ConflictException if duplicate message detected.
   * @returns The created direct message object.
   */
  async sendMessage(
    senderId: string,
    senderEmail: string,
    senderName: string,
    dto: SendDmDto,
  ) {
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
      senderEmail,
      senderName,
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
    const { messageId, idempotencyKey } = dto;

    const canProceed =
      await this.idempotencyService.checkAndSet(idempotencyKey);
    if (!canProceed) {
      throw new ConflictException(
        'Duplicate request. This message has already been marked delievered.',
      );
    }

    const result = await this.prisma.directMessage.updateMany({
      where: {
        id: messageId,
        isDelivered: false,
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
    const { messageId, idempotencyKey } = dto;

    const canProceed =
      await this.idempotencyService.checkAndSet(idempotencyKey);
    if (!canProceed) {
      throw new ConflictException(
        'Duplicate request. This message has already been read.',
      );
    }
    const result = await this.prisma.directMessage.updateMany({
      where: {
        id: messageId,
        isRead: false,
        conversation: {
          participants: {
            some: {
              id: readerId,
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

  // **FIXED and IMPROVED METHOD**
  async editMessage(userId: string, dto: EditDmDto): Promise<EditDmResult> {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException('Duplicate edit request.');
    }

    return this.prisma.$transaction(async (tx) => {
      const message = await tx.directMessage.findUnique({
        where: { id: dto.messageId },
        include: {
          conversation: {
            select: { participants: { select: { id: true } } },
          },
        },
      });

      if (!message) {
        throw new NotFoundException('Message not found.');
      }
      if (message.senderId !== userId) {
        throw new ForbiddenException('You can only edit your own messages.');
      }

      const timeSinceSent =
        (new Date().getTime() - message.timestamp.getTime()) / 1000;
      if (timeSinceSent > this.EDIT_WINDOW_SECONDS) {
        throw new ForbiddenException(
          `Messages can only be edited within ${
            this.EDIT_WINDOW_SECONDS / 60
          } minutes.`,
        );
      }

      const existingMetadata = (message.metadata || {}) as Record<string, any>;
      const newMetadata = {
        ...existingMetadata,
        isEdited: true,
        editedAt: new Date().toISOString(),
      };

      const updatedMessage = await tx.directMessage.update({
        where: { id: dto.messageId },
        data: {
          text: dto.newText,
          metadata: newMetadata,
        },
        // This 'include' matches the payload we defined at the top
        include: {
          sender: { select: { id: true, firstName: true, lastName: true } },
        },
      });

      const participantIds = message.conversation.participants.map((p) => p.id);

      const syncPayload = {
        resource: 'DIRECT_MESSAGE',
        action: 'UPDATED',
        payload: updatedMessage,
      };
      void this.publisherService.publish('sync-events', syncPayload);

      return { updatedMessage, participantIds };
    });
  }

  async deleteMessage(
    userId: string,
    dto: DeleteDmDto,
  ): Promise<DeleteDmResult> {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException('Duplicate delete request.');
    }

    const message = await this.prisma.directMessage.findUnique({
      where: { id: dto.messageId },
      include: {
        conversation: {
          select: {
            participants: {
              select: {
                id: true,
              },
            },
          },
        },
      },
    });

    if (!message) {
      throw new NotFoundException('Message not found.');
    }
    if (message.senderId !== userId) {
      throw new ForbiddenException('You can only delete your own messages.');
    }

    await this.prisma.directMessage.delete({ where: { id: dto.messageId } });

    const participantUserIds = message.conversation.participants.map((p) => ({
      userId: p.id,
    }));

    const result = {
      deletedMessageId: message.id,
      conversation: { participants: participantUserIds },
    };

    const syncPayload = {
      resource: 'DIRECT_MESSAGE',
      action: 'DELETED',
      payload: { id: message.id, conversationId: message.conversationId },
    };
    void this.publisherService.publish('sync-events', syncPayload);

    return result;
  }

  /**
   * Finds an existing conversation between two users or creates a new one.
   * Uses connectOrCreate to ensure UserReference records exist.
   * @param senderId - ID of the sender.
   * @param senderEmail - Email of the sender.
   * @param senderName - Name of the sender (firstName).
   * @param recipientId - ID of the recipient.
   * @returns The found or newly created conversation object.
   */
  private async findOrCreateConversation(
    senderId: string,
    senderEmail: string,
    senderName: string,
    recipientId: string,
  ) {
    // First ensure sender UserReference exists
    await this.prisma.userReference.upsert({
      where: { id: senderId },
      update: {},
      create: {
        id: senderId,
        email: senderEmail,
        firstName: senderName,
      },
    });

    // Check if recipient UserReference exists, if not we need to create a placeholder
    // The recipient info will be updated when they send their first message
    const recipientExists = await this.prisma.userReference.findUnique({
      where: { id: recipientId },
    });

    if (!recipientExists) {
      // Create placeholder - will be updated when recipient sends a message
      await this.prisma.userReference.create({
        data: {
          id: recipientId,
          email: `${recipientId}@placeholder.local`, // Placeholder email
          firstName: 'User',
        },
      });
    }

    let conversation = await this.prisma.conversation.findFirst({
      where: {
        AND: [
          { participants: { some: { id: senderId } } },
          { participants: { some: { id: recipientId } } },
        ],
      },
    });

    if (!conversation) {
      conversation = await this.prisma.conversation.create({
        data: {
          participants: {
            connect: [{ id: senderId }, { id: recipientId }],
          },
        },
      });
    }

    return conversation;
  }

  /**
   * Gets all conversations for a user with their last message and unread count.
   * @param userId - ID of the user.
   * @returns Array of conversations with metadata.
   */
  async getConversations(userId: string) {
    const conversations = await this.prisma.conversation.findMany({
      where: {
        participants: {
          some: { id: userId },
        },
      },
      include: {
        participants: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
          },
        },
        messages: {
          orderBy: { timestamp: 'desc' },
          take: 1,
          include: {
            sender: {
              select: { id: true, firstName: true, lastName: true },
            },
          },
        },
      },
      orderBy: {
        updatedAt: 'desc',
      },
    });

    // Transform to include unread count and format for frontend
    const result = await Promise.all(
      conversations.map(async (conv) => {
        const unreadCount = await this.prisma.directMessage.count({
          where: {
            conversationId: conv.id,
            isRead: false,
            NOT: { senderId: userId },
          },
        });

        // Find the other participant (recipient)
        const recipient = conv.participants.find((p) => p.id !== userId);

        return {
          id: conv.id,
          recipientId: recipient?.id || '',
          recipient: recipient
            ? {
                id: recipient.id,
                firstName: recipient.firstName || 'User',
                lastName: recipient.lastName || '',
                email: recipient.email,
              }
            : null,
          lastMessage: conv.messages[0] || null,
          unreadCount,
          updatedAt: conv.updatedAt.toISOString(),
        };
      }),
    );

    return result;
  }

  /**
   * Gets messages for a specific conversation.
   * @param userId - ID of the requesting user (must be a participant).
   * @param conversationId - ID of the conversation.
   * @param limit - Maximum number of messages to return.
   * @param before - Cursor for pagination (message ID).
   * @returns Array of messages.
   */
  async getMessages(
    userId: string,
    conversationId: string,
    limit = 50,
    before?: string,
  ) {
    // Verify user is a participant
    const conversation = await this.prisma.conversation.findFirst({
      where: {
        id: conversationId,
        participants: {
          some: { id: userId },
        },
      },
    });

    if (!conversation) {
      throw new ForbiddenException(
        'You are not a participant of this conversation.',
      );
    }

    const whereClause: any = {
      conversationId,
    };

    if (before) {
      const beforeMessage = await this.prisma.directMessage.findUnique({
        where: { id: before },
        select: { timestamp: true },
      });
      if (beforeMessage) {
        whereClause.timestamp = { lt: beforeMessage.timestamp };
      }
    }

    const messages = await this.prisma.directMessage.findMany({
      where: whereClause,
      orderBy: { timestamp: 'desc' },
      take: limit,
      include: {
        sender: {
          select: { id: true, firstName: true, lastName: true },
        },
      },
    });

    // Return in chronological order
    return messages.reverse();
  }
}
