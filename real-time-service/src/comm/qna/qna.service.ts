import {
  ConflictException,
  ForbiddenException,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { AskQuestionDto } from './dto/ask-question.dto';
import { UpvoteQuestionDto } from './dto/upvote-question.dto';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { Prisma } from '@prisma/client';
import { ModerateQuestionDto } from './dto/moderate-question.dto';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/shared.module';
import { Inject } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import { UserDataDto } from 'src/common/dto/user-data.dto';
import { PublisherService } from 'src/shared/services/publisher.service';

@Injectable()
export class QnaService {
  private readonly logger = new Logger(QnaService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly httpService: HttpService,
    private readonly publisherService: PublisherService,
  ) {}

  /**
   * Creates a new question within a session.
   * This is the first point of contact for a user's data with this service,
   * so we ensure a local reference for the user exists.
   *
   * @param userId The ID of the user asking the question.
   * @param userEmail The email of the user (from JWT).
   * @param sessionId The ID of the session where the question is asked.
   * @param dto The data for the new question.
   * @returns The newly created question object.
   */
  async askQuestion(
    userId: string,
    userEmail: string,
    sessionId: string,
    dto: AskQuestionDto,
  ) {
    // --- IDEMPOTENCY CHECK ---
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      this.logger.warn(
        `Duplicate request detected for 'askQuestion' with key: ${dto.idempotencyKey}`,
      );
      throw new ConflictException(
        'Duplicate request. This action has already been processed.',
      );
    }

    // In a microservice architecture, we can't assume the user exists
    // in our DB. This command creates a local reference if one doesn't exist.
    await this.findOrCreateUserReference(userId, userEmail);

    this.logger.log(
      `Creating question in session ${sessionId} for user ${userId}`,
    );

    const question = await this.prisma.question.create({
      data: {
        text: dto.text,
        isAnonymous: dto.isAnonymous ?? false,
        sessionId,
        authorId: userId,
        // Default status is 'pending' as per the schema
      },
      include: {
        // We include the author's reference data for the response
        author: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
          },
        },
      },
    });

    // REFINED: Use the helper and correct event type
    void this._publishAnalyticsEvent('QUESTION_ASKED', { sessionId });

    // --- NEW: PUBLISH TO STREAM for the Oracle AI ---
    void this.publisherService.publish(
      'platform.events.qna.question.v1',
      question,
    );

    return question;
  }

  /**
   * Records a user's upvote for a specific question.
   * Includes business logic to prevent self-voting and double-voting.
   *
   * @param userId The ID of the user casting the upvote.
   * @param dto Contains the questionId for the upvote.
   * @returns The question with its updated upvote count.
   */
  async upvoteQuestion(userId: string, dto: UpvoteQuestionDto) {
    // TODO: Implement idempotency check using Redis for the dto.idempotencyKey

    const { questionId } = dto;

    // First, retrieve the question to perform validation checks.
    const question = await this.prisma.question.findUnique({
      where: { id: questionId },
    });

    if (!question) {
      throw new NotFoundException(`Question with ID ${questionId} not found.`);
    }

    // BUSINESS RULE: Users cannot upvote their own questions.
    if (question.authorId === userId) {
      throw new ForbiddenException('Users cannot upvote their own questions.');
    }

    try {
      // ATOMIC OPERATION: Create the upvote record.
      // The composite primary key in our schema (`@@id([userId, questionId])`)
      // automatically prevents a user from creating a second upvote.
      // If they try, Prisma will throw a unique constraint violation error.
      await this.prisma.questionUpvote.create({
        data: {
          questionId,
          userId,
        },
      });
    } catch (error) {
      // This error code indicates a unique constraint violation.
      if (
        error instanceof Prisma.PrismaClientKnownRequestError &&
        error.code === 'P2002'
      ) {
        // The user has already upvoted this question. This is not an error
        // in our system, but we should inform them.
        throw new ConflictException('You have already upvoted this question.');
      }
      // Re-throw any other unexpected database errors.
      throw error;
    }

    this.logger.log(`User ${userId} upvoted question ${questionId}`);
    // REFINED: Use the helper and correct event type
    // We need the sessionId from the question object for the event payload.
    const questionForEvent = await this.getQuestionWithUpvoteCount(
      dto.questionId,
    );
    if (questionForEvent) {
      void this._publishAnalyticsEvent('QUESTION_UPVOTED', {
        sessionId: questionForEvent.sessionId,
      });

      // --- NEW: PUBLISH TO STREAM for the Oracle AI ---
      const upvotePayload = {
        userId,
        questionId: dto.questionId,
        sessionId: questionForEvent.sessionId,
        upvoteTimestamp: new Date().toISOString(),
      };
      void this.publisherService.publish(
        'platform.events.qna.upvote.v1',
        upvotePayload,
      );
    }
    return questionForEvent;
  }

  /**
   * Updates the status of a question (e.g., approves or dismisses it).
   * This is a protected action intended for moderators/admins.
   *
   * @param dto Contains the questionId and the new status.
   * @returns The question with its updated status.
   */
  async moderateQuestion(dto: ModerateQuestionDto) {
    const { questionId, status } = dto;

    // --- IDEMPOTENCY CHECK ---
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      this.logger.warn(
        `Duplicate request detected for 'moderateQuestion' with key: ${dto.idempotencyKey}`,
      );
      throw new ConflictException(
        'Duplicate request. This action has already been processed.',
      );
    }

    this.logger.log(`Moderating question ${questionId} to status: ${status}`);

    // Atomically update the question's status in the database.
    // The 'update' operation will fail if the question doesn't exist,
    // which implicitly handles the 'NotFound' case.
    try {
      const updatedQuestion = await this.prisma.question.update({
        where: { id: questionId },
        data: {
          status: status,
        },
      });

      // --- ADD SYNC EVENT ---
      const syncPayload = {
        resource: 'QUESTION',
        action: 'UPDATED',
        payload: updatedQuestion,
      };
      void this.publisherService.publish('sync-events', syncPayload);
      // After updating, fetch it again with the upvote count for the response.
      return this.getQuestionWithUpvoteCount(updatedQuestion.id);
    } catch (error) {
      if (
        error instanceof Prisma.PrismaClientKnownRequestError &&
        error.code === 'P2025'
      ) {
        // P2025 is the error for 'Record to update not found.'
        throw new NotFoundException(
          `Question with ID ${questionId} not found.`,
        );
      }
      throw error;
    }
  }

  /**
   * Retrieves a single question and includes the real-time count of its upvotes.
   * @param questionId The ID of the question to retrieve.
   */
  private async getQuestionWithUpvoteCount(questionId: string) {
    return this.prisma.question.findUnique({
      where: { id: questionId },
      include: {
        // Include the author's basic info for display
        author: {
          select: { id: true, firstName: true, lastName: true },
        },
        // Prisma's '_count' feature is highly efficient for this.
        _count: {
          select: { upvotes: true },
        },
      },
    });
  }

  /**
   * Finds a user reference by ID or creates a new one.
   * In a complete system, this might involve an internal API call or a
   * message queue event from the User service to get the latest user details.
   *
   * @param userId The user's unique ID.
   * @param email The user's email.
   * @returns The found or created user reference.
   */
  private async findOrCreateUserReference(userId: string, email: string) {
    const existingRef = await this.prisma.userReference.findUnique({
      where: { id: userId },
    });
    if (existingRef) {
      return existingRef;
    }

    // --- FIX: Fetch real user data from the User & Org service ---
    try {
      const userOrgServiceUrl =
        process.env.USER_ORG_SERVICE_URL || 'http://localhost:3001';
      const response = await firstValueFrom(
        this.httpService.get<UserDataDto>(
          `${userOrgServiceUrl}/internal/users/${userId}`,
          {
            headers: { 'X-Internal-Api-Key': process.env.INTERNAL_API_KEY },
          },
        ),
      );

      const userData = response.data;
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
        `Failed to fetch user data for ${userId}. Creating with default values.`,
        error,
      );
      // Fallback in case the User service is down
      return this.prisma.userReference.create({
        data: {
          id: userId,
          email: email,
          firstName: 'Guest',
          lastName: 'User',
        },
      });
    }
  }

  // This is a new private helper to get session metadata from the cache.
  private async _getSessionMetadata(
    sessionId: string,
  ): Promise<{ eventId: string; organizationId: string }> {
    const redisKey = `session:info:${sessionId}`;
    const cachedData = await this.redis.get(redisKey);

    if (cachedData) {
      return JSON.parse(cachedData);
    }

    // If not in cache, we would need to fetch it from the database as a fallback.
    // For now, we'll return placeholders, but the caching logic is in place.
    this.logger.warn(`Session metadata for ${sessionId} not found in cache.`);
    return {
      eventId: 'fallback-event-id',
      organizationId: 'fallback-org-id',
    };
  }
  // --- NEW: Safe, private helper for publishing events ---
  private async _publishAnalyticsEvent(
    type: string,
    data: { sessionId: string },
  ) {
    try {
      // --- FIX: Fetch real metadata instead of using placeholders ---
      const metadata = await this._getSessionMetadata(data.sessionId);
      const eventPayload = {
        type,
        sessionId: data.sessionId,
        eventId: metadata.eventId,
        organizationId: metadata.organizationId,
      };
      await this.redis.publish(
        'analytics-events',
        JSON.stringify(eventPayload),
      );
    } catch (error) {
      this.logger.error('Failed to publish analytics event', error);
    }
  }
}
