import {
  ConflictException,
  ForbiddenException,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { SendMessageDto } from './dto/send-message.dto';
import { EditMessageDto } from './dto/edit-message.dto';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/shared.module';
import { Inject } from '@nestjs/common';
import { AuditLogPayload } from 'src/common/interfaces/audit.interface';
import { PublisherService } from 'src/shared/services/publisher.service';
import { isSessionMetadata } from 'src/common/utils/session.utils';
import { SessionMetadata } from 'src/common/interfaces/session.interface';
import { ReactToMessageDto } from './dto/react-to-message.dto';
import { GamificationService } from 'src/gamification/gamification.gateway';
import { Prisma } from '@prisma/client';

@Injectable()
export class ChatService {
  private readonly logger = new Logger(ChatService.name);
  private readonly EDIT_WINDOW_SECONDS = 300; // 5 minutes

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis, // <-- INJECT REDIS
    private readonly publisherService: PublisherService,
    private readonly gamificationService: GamificationService,
  ) {}

  /**
   * Sends a chat message in a session after idempotency and session checks.
   * Broadcasts sync and analytics events, and publishes to an external stream.
   *
   * @param authorId - ID of the user sending the message.
   * @param sessionId - ID of the chat session.
   * @param dto - DTO containing message content and idempotency key.
   * @returns The newly created message.
   * @throws ConflictException, NotFoundException
   */
  async sendMessage(authorId: string, sessionId: string, dto: SendMessageDto) {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException('Duplicate message request.');
    }

    const session = await this.prisma.chatSession.findUnique({
      where: { id: sessionId },
      select: { participants: true },
    });
    if (!session) {
      throw new NotFoundException('Session not found.');
    }

    // --- REFACTOR to use a transaction ---
    const newMessage = await this.prisma.$transaction(async (tx) => {
      // 1. Create the message
      const createdMessage = await tx.message.create({
        data: { text: dto.text, authorId, sessionId },
        include: {
          author: { select: { id: true, firstName: true, lastName: true } },
        },
      });

      // 2. Create a plain, serializable object from the Prisma result.
      const plainMessagePayload = {
        id: createdMessage.id,
        text: createdMessage.text,
        timestamp: createdMessage.timestamp,
        isEdited: false,
        editedAt: null,
        authorId: createdMessage.authorId,
        sessionId: createdMessage.sessionId,
        author: {
          id: createdMessage.author.id,
          firstName: createdMessage.author.firstName,
          lastName: createdMessage.author.lastName,
        },
      };

      // 2. Create SyncLog entries for ALL participants in the session
      const syncLogPayload = {
        resource: 'MESSAGE',
        action: 'CREATED',
        payload: plainMessagePayload,
      };
      await tx.syncLog.createMany({
        data: session.participants.map((userId) => ({
          userId: userId,
          ...syncLogPayload,
        })),
      });

      return createdMessage;
    });

    // --- NEW GAMIFICATION LOGIC ---
    // After the message is successfully created, award points to the author.
    // We use `void` because we don't need to wait for this to complete
    // before returning the message to the user.
    void this.gamificationService.awardPoints(
      authorId,
      sessionId,
      'MESSAGE_SENT',
    );
    // --- END OF NEW LOGIC ---

    // --- REFINED LOGIC: Use the safe, fire-and-forget helper ---
    void this._publishAnalyticsEvent('MESSAGE_SENT', { sessionId });

    // --- NEW LOGIC: PUBLISH TO STREAM for the Oracle AI ---
    // The stream name comes directly from our spec.
    const streamName = 'platform.events.chat.message.v1';
    void this.publisherService.publish(streamName, newMessage);

    // --- NEW LOGIC: PUBLISH SYNC EVENT ---
    const syncPayload = {
      resource: 'MESSAGE',
      action: 'CREATED',
      payload: newMessage,
    };
    // Publish to the generic sync channel
    void this.publisherService.publish('sync-events', syncPayload);

    return newMessage;
  }

  /**
   * Edits a message within a fixed time window and validates user ownership.
   * Publishes sync update events to downstream consumers.
   *
   * @param userId - ID of the user requesting the edit.
   * @param dto - DTO with messageId, new text, and idempotency key.
   * @returns The updated message object.
   * @throws ConflictException, ForbiddenException, NotFoundException
   */
  async editMessage(userId: string, dto: EditMessageDto) {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException('Duplicate edit request.');
    }

    const message = await this.prisma.message.findUnique({
      where: { id: dto.messageId },
    });

    if (!message) {
      throw new NotFoundException('Message not found.');
    }

    if (message.authorId !== userId) {
      throw new ForbiddenException('You can only edit your own messages.');
    }

    const timeSinceSent =
      (new Date().getTime() - message.timestamp.getTime()) / 1000;
    if (timeSinceSent > this.EDIT_WINDOW_SECONDS) {
      throw new ForbiddenException(
        `Messages can only be edited within ${this.EDIT_WINDOW_SECONDS / 60} minutes.`,
      );
    }

    const updatedMessage = this.prisma.message.update({
      where: { id: dto.messageId },
      data: {
        text: dto.newText,
        metadata: { isEdited: true, editedAt: new Date() }, // Using metadata for flags
      },
      include: {
        author: { select: { id: true, firstName: true, lastName: true } },
      },
    });

    // --- NEW LOGIC: PUBLISH SYNC EVENT FOR UPDATE ---
    const syncPayload = {
      resource: 'MESSAGE',
      action: 'UPDATED',
      payload: updatedMessage,
    };
    void this.publisherService.publish('sync-events', syncPayload);
    return updatedMessage;
  }

  /**
   * Deletes a message if the user has appropriate permissions (own or any).
   * Emits sync and audit events for deletion tracking.
   *
   * @param deleterId - ID of the user requesting deletion.
   * @param messageId - ID of the message to delete.
   * @param permissions - User's permission strings for deletion.
   * @returns Object containing deletedMessageId and sessionId.
   * @throws NotFoundException, ForbiddenException
   */
  async deleteMessage(
    deleterId: string,
    messageId: string,
    permissions: string[] = [],
  ) {
    const message = await this.prisma.message.findUnique({
      where: { id: messageId },
    });

    if (!message) {
      throw new NotFoundException('Message not found.');
    }

    const isAuthor = message.authorId === deleterId;
    const canSelfDelete = permissions.includes('chat:delete:own');
    const canModeratorDelete = permissions.includes('chat:delete:any');

    if (!canModeratorDelete && !(isAuthor && canSelfDelete)) {
      throw new ForbiddenException(
        'You do not have permission to delete this message.',
      );
    }

    await this.prisma.message.delete({
      where: { id: messageId },
    });

    // Fetch the session metadata to get the real organizationId
    const metadata = await this._getSessionMetadata(message.sessionId);

    // --- NEW LOGIC: PUBLISH SYNC EVENT FOR DELETION ---
    const syncPayload = {
      resource: 'MESSAGE',
      action: 'DELETED',
      // For a deletion, the payload just needs the ID
      payload: { id: messageId, sessionId: message.sessionId },
    };
    void this.publisherService.publish('sync-events', syncPayload);

    this.logger.log(`Message ${messageId} deleted by user ${deleterId}`);

    // --- NEW LOGIC: PUBLISH AUDIT EVENT ---
    const auditPayload: AuditLogPayload = {
      action: 'CHAT_MESSAGE_DELETED',
      actingUserId: deleterId,
      organizationId: metadata.organizationId,
      sessionId: message.sessionId,
      details: {
        deletedMessageId: message.id,
        originalAuthorId: message.authorId,
      },
    };
    void this._publishAuditEvent(auditPayload);

    return { deletedMessageId: messageId, sessionId: message.sessionId };
  }

  /**
   * Publishes an audit log event to Redis.
   *
   * @param payload - Structured audit log payload.
   * @private
   */
  private async _publishAuditEvent(payload: AuditLogPayload) {
    try {
      await this.redis.publish('audit-events', JSON.stringify(payload));
    } catch (error) {
      this.logger.error('Failed to publish audit event', error);
    }
  }

  /**
   * Retrieves session metadata from Redis or falls back to database.
   * Re-caches result on DB fetch.
   *
   * @param sessionId - Session ID to fetch metadata for.
   * @returns Session metadata including eventId and organizationId.
   * @throws NotFoundException
   * @private
   */
  private async _getSessionMetadata(
    sessionId: string,
  ): Promise<SessionMetadata> {
    const redisKey = `session:info:${sessionId}`;
    const cachedData = await this.redis.get(redisKey);

    if (cachedData) {
      try {
        const parsedData: unknown = JSON.parse(cachedData);
        if (isSessionMetadata(parsedData)) {
          return parsedData;
        }
      } catch (error) {
        this.logger.warn(
          `Invalid session metadata in cache for ${sessionId}`,
          error,
        );
      }
    }

    // --- FALLBACK: If cache miss or invalid, fetch from PostgreSQL ---
    this.logger.warn(
      `Session metadata for ${sessionId} not found in cache. Fetching from DB.`,
    );
    const session = await this.prisma.chatSession.findUnique({
      where: { id: sessionId },
      select: { eventId: true, organizationId: true },
    });

    if (!session) {
      throw new NotFoundException(
        `Session with ID ${sessionId} not found in primary database.`,
      );
    }

    // Re-populate the cache for the next request
    await this.redis.set(redisKey, JSON.stringify(session), 'EX', 3600); // Cache for 1 hour

    return session;
  }

  /**
   * Publishes an analytics event to Redis with session metadata.
   * Called in fire-and-forget style from public methods.
   *
   * @param type - Event type identifier.
   * @param data - Payload with sessionId.
   * @private
   */
  private async _publishAnalyticsEvent(
    type: string,
    data: { sessionId: string },
  ) {
    try {
      const metadata = await this._getSessionMetadata(data.sessionId);
      const eventPayload = {
        type,
        sessionId: data.sessionId,
        eventId: metadata.eventId,
        organizationId: metadata.organizationId,
      };
      // We await inside this helper, but we don't await the helper itself.
      await this.redis.publish(
        'analytics-events',
        JSON.stringify(eventPayload),
      );
    } catch (error) {
      this.logger.error('Failed to publish analytics event', error);
    }
  }

  /**
   * Adds or removes an emoji reaction from a specific message for a user.
   * This method implements a toggle: reacting a second time with the same emoji
   * will remove the reaction.
   */
  async reactToMessage(userId: string, dto: ReactToMessageDto) {
    const { messageId, emoji } = dto;

    const existingReaction = await this.prisma.messageReaction.findUnique({
      where: {
        userId_messageId_emoji: {
          userId,
          messageId,
          emoji,
        },
      },
    });

    if (existingReaction) {
      // If the reaction exists, the user is toggling it off.
      await this.prisma.messageReaction.delete({
        where: {
          userId_messageId_emoji: {
            userId,
            messageId,
            emoji,
          },
        },
      });
      this.logger.log(
        `User ${userId} removed reaction '${emoji}' from message ${messageId}`,
      );
    } else {
      // If it doesn't exist, create it.
      // We wrap this in a try/catch to handle the rare case where the message might be deleted
      // between the client's action and our database operation.
      try {
        await this.prisma.messageReaction.create({
          data: {
            userId,
            messageId,
            emoji,
          },
        });
        this.logger.log(
          `User ${userId} added reaction '${emoji}' to message ${messageId}`,
        );
      } catch (error) {
        // P2003: Foreign key constraint failed (e.g., the messageId doesn't exist)
        if (
          error instanceof Prisma.PrismaClientKnownRequestError &&
          error.code === 'P2003'
        ) {
          throw new NotFoundException(
            `Message with ID ${messageId} not found.`,
          );
        }
        throw error;
      }
    }

    // After changing a reaction, fetch the updated message with aggregated reaction counts
    return this._getMessageWithReactions(messageId);
  }

  /**
   * Private helper to fetch a message and its aggregated reactions.
   * This provides a clean payload to broadcast back to clients.
   */
  private async _getMessageWithReactions(messageId: string) {
    const message = await this.prisma.message.findUnique({
      where: { id: messageId },
      include: {
        author: { select: { id: true, firstName: true, lastName: true } },
        // Include the raw reaction data
        reactions: {
          select: {
            emoji: true,
            userId: true,
          },
        },
      },
    });

    if (!message) {
      return null;
    }

    // Aggregate the raw reactions into a count map
    const reactionsSummary = message.reactions.reduce(
      (acc, reaction) => {
        acc[reaction.emoji] = (acc[reaction.emoji] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>,
    );

    // Return the message object along with the clean summary
    return {
      ...message,
      reactionsSummary, // e.g., { "👍": 3, "❤️": 1 }
    };
  }
}
