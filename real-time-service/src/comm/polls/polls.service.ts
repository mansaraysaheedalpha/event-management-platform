//src/comm/polls/polls.service.ts
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
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { Inject } from '@nestjs/common';
import { AuditLogPayload } from 'src/common/interfaces/audit.interface';
import { PublisherService } from 'src/shared/services/publisher.service';
import { SessionValidationService } from 'src/shared/services/session-validation.service';
import { isSessionMetadata } from 'src/common/utils/session.utils';
import { SessionMetadata } from 'src/common/interfaces/session.interface';
import { GamificationService } from 'src/gamification/gamification.service';
import { StartGiveawayDto } from './dto/start-giveaway.dto';

@Injectable()
export class PollsService {
  private readonly logger = new Logger(PollsService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis, // Redis client for caching and messaging
    private readonly publisherService: PublisherService, // Publishes events to message bus
    private readonly sessionValidationService: SessionValidationService,
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

    // Validate that the user is a participant in this session
    await this.sessionValidationService.validateSessionMembership(
      creatorId,
      sessionId,
    );

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
    let pollSessionId: string | undefined;
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

      pollSessionId = poll.sessionId;
      this.logger.log(
        `User ${userId} voted for option ${optionId} in poll ${pollId}`,
      );
      // 4. After a successful vote, fetch the poll again with the complete,
      // updated results to be broadcasted.
      return this.getPollWithResults(dto.pollId, userId, tx);
    });

    // Award gamification points outside the transaction to avoid rollback on failure
    if (pollSessionId) {
      try {
        await this.gamificationService.awardPoints(
          userId,
          pollSessionId,
          'POLL_VOTED',
        );
      } catch (err) {
        this.logger.warn(
          `Gamification points could not be awarded for user ${userId} in poll ${pollId}: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
    }

    // This code now works correctly because `pollWithResults` is the resolved object.
    if (pollWithResults) {
      // REFINED: Use the helper and correct event type
      void this._publishAnalyticsEvent('POLL_VOTE_CAST', {
        sessionId: pollWithResults.poll.sessionId,
        pollId: pollWithResults.poll.id,
      });
      // --- NEW: PUBLISH TO STREAM for the Oracle AI ---
      const votePayload = {
        userId,
        pollId: dto.pollId,
        optionId: dto.optionId,
        sessionId: pollWithResults.poll.sessionId,
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
    userId?: string,
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

    const publicPollData = { ...poll, options: optionsWithVotes, totalVotes };

    // 2. If a userId is provided, find their specific vote
    let userVoteId: string | null = null;
    if (userId) {
      const userVote = await tx.pollVote.findUnique({
        where: {
          userId_pollId: {
            userId,
            pollId,
          },
        },
        select: { optionId: true },
      });
      userVoteId = userVote?.optionId || null;
    }

    // 3. Return the data in the "envelope" structure from our spec
    return {
      poll: publicPollData,
      userVotedForOptionId: userVoteId,
    };
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
      const metadata = await this._getSessionMetadata(poll.sessionId);

      // --- NEW LOGIC: PUBLISH AUDIT EVENT ---
      const auditPayload: AuditLogPayload = {
        action: 'POLL_CLOSED',
        actingUserId: hostId,
        organizationId: metadata.organizationId,
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

  /**
   * Selects a random winner from users who voted for a specific poll option.
   * Giveaways can only be run on closed polls to ensure all votes are in.
   */
  async selectGiveawayWinner(dto: StartGiveawayDto, adminId: string) {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException('Duplicate request.');
    }

    // Verify the poll exists and is closed before running giveaway
    const poll = await this.prisma.poll.findUnique({
      where: { id: dto.pollId },
      select: { isActive: true },
    });

    if (!poll) {
      throw new NotFoundException(`Poll with ID ${dto.pollId} not found.`);
    }

    if (poll.isActive) {
      throw new ForbiddenException(
        'Giveaway can only be run on closed polls. Please close the poll first.',
      );
    }

    // 1. Get all users who voted for the winning option
    const voters = await this.prisma.pollVote.findMany({
      where: {
        pollId: dto.pollId,
        optionId: dto.winningOptionId,
      },
      select: {
        userId: true,
      },
    });

    if (voters.length === 0) {
      this.logger.warn(
        `No voters found for option ${dto.winningOptionId} in poll ${dto.pollId}. No winner selected.`,
      );
      return null;
    }

    // 2. Select a random winner
    const winnerIndex = Math.floor(Math.random() * voters.length);
    const winnerId = voters[winnerIndex].userId;

    // 3. Fetch winner's details and session details for the payload
    const [winnerDetails, pollDetails] = await Promise.all([
      this.prisma.userReference.findUnique({
        where: { id: winnerId },
        select: { id: true, firstName: true, lastName: true },
      }),
      this.prisma.poll.findUnique({
        where: { id: dto.pollId },
        select: { sessionId: true },
      }),
    ]);

    if (!pollDetails) {
      throw new NotFoundException(`Poll with ID ${dto.pollId} not found.`);
    }

    // --- THIS IS THE FIX ---
    // 4. Fetch the real metadata using our helper to get the organizationId
    const metadata = await this._getSessionMetadata(pollDetails.sessionId);

    // 5. Publish an audit event with the real organizationId
    const auditPayload: AuditLogPayload = {
      action: 'GIVEAWAY_WINNER_SELECTED',
      actingUserId: adminId,
      organizationId: metadata.organizationId, // <-- Placeholder removed
      sessionId: pollDetails.sessionId,
      details: {
        pollId: dto.pollId,
        winningOptionId: dto.winningOptionId,
        winnerId,
      },
    };
    void this._publishAuditEvent(auditPayload);

    this.logger.log(
      `User ${winnerId} selected as giveaway winner for poll ${dto.pollId}`,
    );

    return {
      pollId: dto.pollId,
      winner: winnerDetails,
      prize: dto.prize, // Prize details could be added to the DTO
    };
  }

  /**
   * Gets all polls for a session with their current results.
   * Used to send poll history when a user joins a session.
   *
   * @param sessionId - The session to fetch polls for.
   * @param userId - Optional user ID to include their vote status.
   * @returns Array of polls with results and user vote status.
   */
  async getSessionPolls(sessionId: string, userId?: string) {
    // Fetch all polls for this session
    const polls = await this.prisma.poll.findMany({
      where: { sessionId },
      include: {
        options: true,
        creator: {
          select: { id: true, firstName: true, lastName: true },
        },
      },
      orderBy: { createdAt: 'desc' },
    });

    // For each poll, calculate vote counts and check user's vote
    const pollsWithResults = await Promise.all(
      polls.map(async (poll) => {
        // Get vote counts for each option
        const voteCounts = await this.prisma.pollVote.groupBy({
          by: ['optionId'],
          where: { pollId: poll.id },
          _count: { optionId: true },
        });

        // Map vote counts to options
        const optionsWithVotes = poll.options.map((option) => {
          const count =
            voteCounts.find((vc) => vc.optionId === option.id)?._count
              .optionId || 0;
          return { ...option, voteCount: count };
        });

        // Calculate total votes
        const totalVotes = optionsWithVotes.reduce(
          (sum, opt) => sum + opt.voteCount,
          0,
        );

        // Check if user has voted
        let userVotedForOptionId: string | null = null;
        if (userId) {
          const userVote = await this.prisma.pollVote.findUnique({
            where: {
              userId_pollId: { userId, pollId: poll.id },
            },
            select: { optionId: true },
          });
          userVotedForOptionId = userVote?.optionId || null;
        }

        return {
          poll: {
            ...poll,
            options: optionsWithVotes,
            totalVotes,
          },
          userVotedForOptionId,
        };
      }),
    );

    return pollsWithResults;
  }
}
