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
import { ModerateQuestionDto } from './dto/moderate-question.dto';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/shared.module';
import { Inject } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import { UserDataDto } from 'src/common/dto/user-data.dto';
import { PublisherService } from 'src/shared/services/publisher.service';
import { isSessionMetadata } from 'src/common/utils/session.utils';
import { SessionMetadata } from 'src/common/interfaces/session.interface';
import { AnswerQuestionDto } from './dto/answer-question.dto';
import { GamificationService } from 'src/gamification/gamification.gateway';

@Injectable()
export class QnaService {
  private readonly logger = new Logger(QnaService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly httpService: HttpService,
    private readonly publisherService: PublisherService,
      private readonly gamificationService: GamificationService,
  ) {}

  /**
   * Creates a new question within a session.
   * Ensures a user reference exists locally before creating the question.
   * Enforces idempotency to avoid duplicate questions.
   * @param userId The ID of the user asking the question.
   * @param userEmail The user's email from JWT.
   * @param sessionId The session ID where the question is asked.
   * @param dto The question data payload.
   * @returns The created question object with author info.
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

     // --- NEW GAMIFICATION LOGIC ---
    void this.gamificationService.awardPoints(
      userId,
      sessionId,
      'QUESTION_ASKED',
    );
    // --- END OF NEW LOGIC ---
    

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

    // --- NEW GAMIFICATION LOGIC ---
    // We need the sessionId, which is on the question object we fetched.
    if (question) {
      void this.gamificationService.awardPoints(
        userId,
        question.sessionId,
        'QUESTION_UPVOTED',
      );
    }
    // --- END OF NEW LOGIC ---

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
   * Allows moderators/admins to update the status of a question (approve/dismiss).
   * Enforces idempotency and handles not found and duplicate requests gracefully.
   * @param dto Contains questionId, new status, and idempotency key.
   * @returns The updated question with upvote count.
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
   * Helper to get a question with its author info and upvote count.
   * @param questionId The question's unique ID.
   * @returns Question including author and upvote count.
   */
  private async getQuestionWithUpvoteCount(questionId: string) {
    return this.prisma.question.findUnique({
      where: { id: questionId },
      include: {
        author: {
          select: { id: true, firstName: true, lastName: true },
        },
        _count: {
          select: { upvotes: true },
        },
        answer: { // <-- INCLUDE THE ANSWER
          include: {
            author: { // Include who answered it
              select: { id: true, firstName: true, lastName: true },
            },
          },
        },
      },
    });
  }
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
   * Publishes an analytics event to Redis channel.
   * Includes session, event, and organization metadata.
   * @param type Type of analytics event.
   * @param data Payload containing sessionId.
   */
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

  /**
   * Adds an official answer to a question.
   * This is a protected action for moderators.
   */
  async answerQuestion(adminId: string, dto: AnswerQuestionDto) {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException('This answer has already been submitted.');
    }

    // Use a transaction to ensure both the answer is created AND
    // the question is marked as answered in one atomic operation.
    const updatedQuestion = await this.prisma.$transaction(async (tx) => {
      // 1. Create the Answer record
      await tx.answer.create({
        data: {
          text: dto.answerText,
          authorId: adminId,
          questionId: dto.questionId,
        },
      });

      // 2. Update the Question to mark it as answered
      return tx.question.update({
        where: { id: dto.questionId },
        data: { isAnswered: true },
      });
    });

    this.logger.log(`Question ${dto.questionId} answered by admin ${adminId}`);

    // Fetch the full question with the new answer included to broadcast
    const finalQuestion = await this.getQuestionWithUpvoteCount(dto.questionId);

    // Publish sync event
    const syncPayload = {
      resource: 'QUESTION',
      action: 'UPDATED',
      payload: finalQuestion,
    };
    void this.publisherService.publish('sync-events', syncPayload);

    return finalQuestion;
  }
}
