import {
  ConflictException,
  ForbiddenException,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { CreatePollDto } from './dto/create-poll.dto';
import { ManagePollDto } from './dto/manage-polls.dto';
import { Prisma } from '@prisma/client';
import { SubmitVoteDto } from './dto/submit-vote.dto';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/shared.module';
import { Inject } from '@nestjs/common';
import { AuditLogPayload } from 'src/common/interfaces/audit.interface';
import { PublisherService } from 'src/shared/services/publisher.service';
import { isSessionMetadata } from 'src/common/utils/session.utils';
import { SessionMetadata } from 'src/common/interfaces/session.interface';
import { GamificationService } from 'src/gamification/gamification.gateway';

@Injectable()
export class PollsService {
  private readonly logger = new Logger(PollsService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis, // Redis client for caching and messaging
    private readonly publisherService: PublisherService, // Publishes events to message bus
    private readonly gamificationService: GamificationService,
  ) {}

  /**
   * Creates a new poll with options inside a session.
   * Uses idempotency key to avoid duplicate poll creation.
   * Uses a database transaction so either all or nothing happens.
   *
   * @param creatorId - User ID who creates the poll.
   * @param sessionId - Session ID where poll belongs.
   * @param dto - Poll details including question and options.
   * @returns The full poll with options and creator info.
   */
  async createPoll(creatorId: string, sessionId: string, dto: CreatePollDto) {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException(
        'Duplicate request. This poll has already been created.',
      );
    }

    this.logger.log(`User ${creatorId} creating poll in session ${sessionId}`);

    // Use a transaction to ensure that if any part fails, the whole operation is rolled back.
    // This guarantees we never have a poll without options.
    return this.prisma.$transaction(async (tx) => {
      // 1. Create the main Poll record
      const poll = await tx.poll.create({
        data: {
          question: dto.question,
          creatorId,
          sessionId,
        },
      });

      // 2. Prepare the options data linked to the new poll's ID
      const optionsData = dto.options.map((option) => ({
        text: option.text,
        pollId: poll.id,
      }));

      // 3. Create all options in a single, efficient query
      await tx.pollOption.createMany({
        data: optionsData,
      });

      // 4. Return the complete poll object with its options
      return tx.poll.findUnique({
        where: { id: poll.id },
        include: {
          options: true, // Include the newly created options
          creator: {
            select: { id: true, firstName: true, lastName: true },
          },
        },
      });
    });
  }

  /**
   * Allows a user to submit a vote on a poll option.
   * Checks for duplicates with idempotency key.
   * Validates that poll exists and is active.
   * Uses transaction for atomicity of vote creation and fetching results.
   * Publishes analytics and event streams after voting.
   *
   * @param userId - ID of the voting user.
   * @param dto - Vote data including pollId, optionId, and idempotencyKey.
   * @returns The poll with updated vote counts.
   */
  async submitVote(userId: string, dto: SubmitVoteDto) {
    const { pollId, optionId, idempotencyKey } = dto;

    const canProceed =
      await this.idempotencyService.checkAndSet(idempotencyKey);
    if (!canProceed) {
      throw new ConflictException(
        'Duplicate request. This vote has already been submitted.',
      );
    }

    // Use a transaction to ensure data consistency. We read the poll's state
    // and write the vote in a single, atomic operation.
    const pollWithResults = await this.prisma.$transaction(async (tx) => {
      // 1. Find the poll to validate its status.
      const poll = await tx.poll.findUnique({
        where: { id: pollId },
      });

      if (!poll) {
        throw new NotFoundException(`Poll with ID ${pollId} not found.`);
      }

      // 2. BUSINESS RULE: Users cannot vote on an inactive poll.
      if (!poll.isActive) {
        throw new ForbiddenException('This poll is no longer active.');
      }

      // 3. Create the vote. The composite key in our schema (`@@id([userId, pollId])`)
      // will automatically throw an error if the user tries to vote a second time.
      try {
        await tx.pollVote.create({
          data: {
            userId,
            pollId,
            optionId,
          },
        });
      } catch (error) {
        if (
          error instanceof Prisma.PrismaClientKnownRequestError &&
          error.code === 'P2002'
        ) {
          throw new ConflictException('You have already voted in this poll.');
        }
        throw error; // Re-throw other unexpected errors.
      }

      // --- NEW GAMIFICATION LOGIC (inside the transaction) ---
      await this.gamificationService.awardPoints(
        userId,
        poll.sessionId,
        'POLL_VOTED',
      );
      // --- END OF NEW LOGIC ---
      this.logger.log(
        `User ${userId} voted for option ${optionId} in poll ${pollId}`,
      );
      // 4. After a successful vote, fetch the poll again with the complete,
      // updated results to be broadcasted.
      return this.getPollWithResults(pollId, tx);
    });

    // This code now works correctly because `pollWithResults` is the resolved object.
    if (pollWithResults) {
      // REFINED: Use the helper and correct event type
      void this._publishAnalyticsEvent('POLL_VOTE_CAST', {
        sessionId: pollWithResults.sessionId,
        pollId: pollWithResults.id,
      });
      // --- NEW: PUBLISH TO STREAM for the Oracle AI ---
      const votePayload = {
        userId,
        pollId: dto.pollId,
        optionId: dto.optionId,
        sessionId: pollWithResults.sessionId,
        voteTimestamp: new Date().toISOString(),
      };
      void this.publisherService.publish(
        'platform.events.poll.vote.v1',
        votePayload,
      );
    }
    return pollWithResults;
  }

  /**
   * Helper method to fetch a poll with vote counts per option.
   * Can run inside or outside a transaction.
   *
   * @param pollId - Poll to fetch.
   * @param tx - Optional Prisma transaction client.
   * @returns Poll data including options with voteCount and totalVotes.
   */
  private async getPollWithResults(
    pollId: string,
    tx: Prisma.TransactionClient = this.prisma,
  ) {
    // 1. Fetch the main poll data and its options.
    const poll = await tx.poll.findUnique({
      where: { id: pollId },
      include: {
        options: true,
      },
    });

    if (!poll) return null;

    // 2. Get the vote counts for each option in a single, efficient query.
    const voteCounts = await tx.pollVote.groupBy({
      by: ['optionId'],
      where: { pollId: pollId },
      _count: {
        optionId: true,
      },
    });

    // 3. Map the vote counts back to the options.
    const optionsWithVotes = poll.options.map((option) => {
      const count =
        voteCounts.find((vc) => vc.optionId === option.id)?._count.optionId ||
        0;
      return { ...option, voteCount: count };
    });

    // 4. Calculate the total number of votes.
    const totalVotes = optionsWithVotes.reduce(
      (sum, option) => sum + option.voteCount,
      0,
    );

    return { ...poll, options: optionsWithVotes, totalVotes };
  }

  /**
   * Manages poll lifecycle actions such as closing a poll.
   * Checks user permissions (only creator allowed).
   * Uses idempotency key to avoid duplicate actions.
   * Publishes audit and sync events.
   *
   * @param hostId - ID of the user managing the poll.
   * @param dto - Management data including pollId, action, and idempotencyKey.
   * @returns Final poll results after management.
   */
  async managePoll(hostId: string, dto: ManagePollDto) {
    const { pollId, action } = dto;

    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException(
        'Duplicate request. This action has already been processed.',
      );
    }

    // Find the poll to verify ownership and status
    const poll = await this.prisma.poll.findUnique({
      where: { id: pollId },
    });

    if (!poll) {
      throw new NotFoundException(`Poll with ID ${pollId} not found.`);
    }

    // --- CRITICAL SECURITY CHECK ---
    // Ensure the user managing the poll is the one who created it.
    if (poll.creatorId !== hostId) {
      throw new ForbiddenException(
        'You do not have permission to manage this poll.',
      );
    }

    if (action === 'close') {
      if (!poll.isActive) {
        this.logger.warn(
          `Attempted to close an already inactive poll: ${pollId}`,
        );
        // If already closed, just return the final results without a DB update.
        return this.getPollWithResults(pollId);
      }

      await this.prisma.poll.update({
        where: { id: pollId },
        data: { isActive: false },
      });

      const finalResults = await this.getPollWithResults(dto.pollId);

      // --- NEW LOGIC: PUBLISH AUDIT EVENT ---
      const auditPayload: AuditLogPayload = {
        action: 'POLL_CLOSED',
        actingUserId: hostId,
        organizationId: 'placeholder-org-id', // We'll resolve placeholders later
        sessionId: poll.sessionId,
        details: {
          pollId: poll.id,
          pollQuestion: poll.question,
        },
      };
      void this._publishAuditEvent(auditPayload);

      // --- NEW: PUBLISH TO STREAM for the Oracle AI and SYSTEM OFFLINE SYNCING ---
      if (finalResults) {
        void this.publisherService.publish(
          'platform.events.poll.closed.v1',
          finalResults,
        );
        const syncPayload = {
          resource: 'POLL',
          action: 'UPDATED',
          payload: finalResults,
        };
        void this.publisherService.publish('sync-events', syncPayload);
      }

      return finalResults;
    }
  }

  /**
   * Publishes audit logs asynchronously to Redis.
   * Catches and logs errors internally.
   *
   * @param payload - Audit log data.
   */
  private async _publishAuditEvent(payload: AuditLogPayload) {
    try {
      await this.redis.publish('audit-events', JSON.stringify(payload));
    } catch (error) {
      this.logger.error('Failed to publish audit event', error);
    }
  }

  /**
   * Retrieves session metadata from Redis cache or DB as fallback.
   * Caches the metadata in Redis for 1 hour.
   *
   * @param sessionId - ID of the session.
   * @returns Session metadata including eventId and organizationId.
   */
  private async _getSessionMetadata(
    sessionId: string,
  ): Promise<SessionMetadata> {
    const redisKey = `session:info:${sessionId}`;
    const cachedData = await this.redis.get(redisKey);

    if (cachedData) {
      try {
        const parsedData: unknown = JSON.parse(cachedData);
        // Use the type guard to validate and return
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
   * Publishes analytics events safely.
   * Fetches session metadata for full context.
   * Logs error on failure but does not block main flow.
   *
   * @param type - Analytics event type string.
   * @param data - Event data containing sessionId and optionally pollId.
   */
  private async _publishAnalyticsEvent(
    type: string,
    data: { sessionId: string; pollId?: string },
  ) {
    try {
      // --- FIX: Fetch real metadata instead of using placeholders ---
      const metadata = await this._getSessionMetadata(data.sessionId);
      const eventPayload = {
        type,
        ...data,
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
