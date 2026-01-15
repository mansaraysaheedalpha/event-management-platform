//src/comm/chat/chat.service.ts
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
import { Inject } from '@nestjs/common';
import { REDIS_CLIENT, SYNC_EVENTS_CHANNEL } from 'src/shared/redis.constants';
import { AuditLogPayload } from 'src/common/interfaces/audit.interface';
import { PublisherService } from 'src/shared/services/publisher.service';
import { isSessionMetadata } from 'src/common/utils/session.utils';
import { SessionMetadata } from 'src/common/interfaces/session.interface';
import { ReactToMessageDto } from './dto/react-to-message.dto';
import { GamificationService } from 'src/gamification/gamification.service';
import { ConfigService } from '@nestjs/config';
import { Prisma } from '@prisma/client';
import { DeleteMessageDto } from './dto/delete-message.dto';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import { UserDataDto } from 'src/common/dto/user-data.dto';

@Injectable()
export class ChatService {
  private readonly logger = new Logger(ChatService.name);
  private readonly EDIT_WINDOW_SECONDS: number;

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly publisherService: PublisherService,
    private readonly gamificationService: GamificationService,
    private readonly configService: ConfigService,
    private readonly httpService: HttpService,
  ) {
    this.EDIT_WINDOW_SECONDS = this.configService.get<number>(
      'CHAT_EDIT_WINDOW_SECONDS',
      300,
    );
  }

  /**
   * Sends a chat message in a session after idempotency and session checks.
   * Broadcasts sync and analytics events, and publishes to an external stream.
   * Auto-creates the ChatSession if it doesn't exist.
   *
   * @param authorId - ID of the user sending the message.
   * @param sessionId - ID of the chat session.
   * @param dto - DTO containing message content and idempotency key.
   * @param eventId - The parent event ID (for auto-creating sessions).
   * @param organizationId - The organization ID (for auto-creating sessions).
   * @returns The newly created message.
   * @throws ConflictException
   */
  async sendMessage(
    authorId: string,
    authorEmail: string,
    sessionId: string,
    dto: SendMessageDto,
    eventId?: string,
    organizationId?: string,
  ) {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException('Duplicate message request.');
    }

    // Ensure the user exists in the UserReference table
    await this.findOrCreateUserReference(authorId, authorEmail);

    // Auto-create ChatSession if it doesn't exist (upsert pattern)
    const session = await this.prisma.chatSession.upsert({
      where: { id: sessionId },
      update: {
        // Add the author to participants if not already present
        participants: {
          push: authorId,
        },
      },
      create: {
        id: sessionId,
        name: `Chat for ${sessionId}`,
        eventId: eventId || sessionId,
        organizationId: organizationId || 'default',
        participants: [authorId],
      },
      select: { participants: true },
    });

    // Deduplicate participants (in case of duplicate pushes)
    const uniqueParticipants = [...new Set(session.participants)];

    // --- REFACTOR to use a transaction ---
    const newMessage = await this.prisma.$transaction(async (tx) => {
      // Update participants to deduplicated list if needed
      if (uniqueParticipants.length !== session.participants.length) {
        await tx.chatSession.update({
          where: { id: sessionId },
          data: { participants: uniqueParticipants },
        });
      }

      // 1. Create the message
      const createdMessage = await tx.message.create({
        data: {
          text: dto.text,
          authorId,
          sessionId,
          replyingToMessageId: dto.replyingToMessageId,
        },
        include: {
          author: { select: { id: true, firstName: true, lastName: true } },
          parentMessage: {
            include: {
              author: { select: { id: true, firstName: true, lastName: true } },
            },
          },
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
        data: uniqueParticipants.map((userId) => ({
          userId: userId,
          ...syncLogPayload,
        })),
      });

      return createdMessage;
    });

    // --- HEATMAP TRACKING (uses Pub/Sub, not Streams) ---
    void this.redis.publish(
      'heatmap-events',
      JSON.stringify({ sessionId, userId: authorId }),
    );
    // --- END HEATMAP LOGIC ---

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

    const updatedMessage = await this.prisma.$transaction(async (tx) => {
      const message = await tx.message.findUnique({
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
          `Messages can only be edited within ${
            this.EDIT_WINDOW_SECONDS / 60
          } minutes.`,
        );
      }

      // **FIX STARTS HERE**
      // The `isEdited` and `editedAt` properties belong inside the metadata object.
      const existingMetadata = (message.metadata || {}) as Record<string, any>;
      const newMetadata = {
        ...existingMetadata,
        isEdited: true,
        editedAt: new Date().toISOString(), // Use ISO string for JSON compatibility
      };

      return tx.message.update({
        where: { id: dto.messageId },
        data: {
          text: dto.newText,
          // The incorrect top-level properties have been removed.
          // All edit-related flags are now correctly placed in the metadata field.
          metadata: newMetadata,
        },
        include: {
          author: { select: { id: true, firstName: true, lastName: true } },
        },
      });
      // **FIX ENDS HERE**
    });

    void this.publisherService.publish(SYNC_EVENTS_CHANNEL, {
      resource: 'MESSAGE',
      action: 'UPDATED',
      payload: updatedMessage,
    });

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
    dto: DeleteMessageDto,
    permissions: string[] = [],
  ) {
    const { messageId, idempotencyKey } = dto;
    const canProceed =
      await this.idempotencyService.checkAndSet(idempotencyKey);
    if (!canProceed) {
      throw new ConflictException(
        'This delete request has already been processed.',
      );
    }
    const message = await this.prisma.message.findUnique({
      where: { id: messageId },
    });

    if (!message) {
      throw new NotFoundException('Message not found.');
    }

    const isAuthor = message.authorId === deleterId;
    const canModeratorDelete = permissions.includes('chat:delete:any');

    // Authors can always delete their own messages, no permission needed
    // Moderators with chat:delete:any can delete anyone's messages
    if (!isAuthor && !canModeratorDelete) {
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
    const { messageId, emoji, idempotencyKey } = dto;

    const canProceed =
      await this.idempotencyService.checkAndSet(idempotencyKey);
    if (!canProceed) {
      throw new ConflictException('This reaction has already been processed.');
    }

    // Track whether a reaction was added (for analytics)
    let reactionAdded = false;
    let messageSessionId: string | null = null;

    await this.prisma.$transaction(async (tx) => {
      const existingReaction = await tx.messageReaction.findUnique({
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
        try {
          // Get the message to obtain sessionId for analytics
          const message = await tx.message.findUnique({
            where: { id: messageId },
            select: { sessionId: true },
          });
          messageSessionId = message?.sessionId || null;

          await this.prisma.messageReaction.create({
            data: {
              userId,
              messageId,
              emoji,
            },
          });
          reactionAdded = true;
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
    });

    // Publish analytics event for reactions added (not removed)
    if (reactionAdded && messageSessionId) {
      void this._publishAnalyticsEvent('REACTION_SENT', { sessionId: messageSessionId });
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

  /**
   * Gets the sessionId for a given message.
   * Used when frontend doesn't send sessionId in reaction requests.
   *
   * @param messageId - The message ID to look up.
   * @returns The sessionId or null if message not found.
   */
  async getMessageSessionId(messageId: string): Promise<string | null> {
    const message = await this.prisma.message.findUnique({
      where: { id: messageId },
      select: { sessionId: true },
    });
    return message?.sessionId || null;
  }

  /**
   * Retrieves chat history for a session.
   * Used when a client joins a session to send them existing messages.
   *
   * @param sessionId - The session ID to get history for.
   * @returns Array of messages with author info and reactions.
   */
  async getSessionHistory(sessionId: string) {
    const messages = await this.prisma.message.findMany({
      where: { sessionId },
      orderBy: { timestamp: 'asc' },
      include: {
        author: { select: { id: true, firstName: true, lastName: true } },
        parentMessage: {
          include: {
            author: { select: { id: true, firstName: true, lastName: true } },
          },
        },
        reactions: {
          select: { emoji: true, userId: true },
        },
      },
    });

    // Transform messages to include reaction summaries
    return messages.map((message) => {
      const reactionsSummary = message.reactions.reduce(
        (acc, reaction) => {
          acc[reaction.emoji] = (acc[reaction.emoji] || 0) + 1;
          return acc;
        },
        {} as Record<string, number>,
      );

      return {
        id: message.id,
        text: message.text,
        timestamp: message.timestamp,
        isEdited: (message.metadata as any)?.isEdited || false,
        editedAt: (message.metadata as any)?.editedAt || null,
        authorId: message.authorId,
        sessionId: message.sessionId,
        author: message.author,
        parentMessage: message.parentMessage,
        reactionsSummary,
      };
    });
  }

  /**
   * Finds or creates a user reference locally.
   * Attempts to fetch user data from the User & Org service, falling back to default values.
   * @param userId User's unique ID.
   * @param email User's email.
   * @returns The existing or newly created user reference.
   */
  private async findOrCreateUserReference(userId: string, email: string) {
    const existingRef = await this.prisma.userReference.findUnique({
      where: { id: userId },
    });

    // Check if existing record has placeholder values that need refreshing
    const hasPlaceholderValues =
      existingRef &&
      (existingRef.firstName === 'Guest' || existingRef.lastName === 'User');

    if (existingRef && !hasPlaceholderValues) {
      return existingRef;
    }

    // Fetch real user data from the User & Org service
    try {
      const userOrgServiceUrl =
        process.env.USER_ORG_SERVICE_URL || 'http://user-and-org-service:3001';
      const response = await firstValueFrom(
        this.httpService.get<UserDataDto>(
          `${userOrgServiceUrl}/internal/users/${userId}`,
          {
            headers: { 'X-Internal-Api-Key': process.env.INTERNAL_API_KEY },
          },
        ),
      );

      const userData = response.data;

      if (existingRef) {
        // Update existing placeholder record with real data
        return this.prisma.userReference.update({
          where: { id: userId },
          data: {
            email: userData.email,
            firstName: userData.first_name,
            lastName: userData.last_name,
          },
        });
      }

      return this.prisma.userReference.create({
        data: {
          id: userId,
          email: userData.email,
          firstName: userData.first_name,
          lastName: userData.last_name,
        },
      });
    } catch (error) {
      this.logger.error(
        `Failed to fetch user data for ${userId}. Using default values.`,
        error,
      );

      if (existingRef) {
        return existingRef; // Keep existing record even if placeholder
      }

      // Fallback in case the User service is down
      return this.prisma.userReference.create({
        data: {
          id: userId,
          email: email || `${userId}@unknown.local`,
          firstName: 'Guest',
          lastName: 'User',
        },
      });
    }
  }
}
