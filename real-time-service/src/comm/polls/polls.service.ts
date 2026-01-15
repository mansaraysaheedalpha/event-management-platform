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
import { KafkaService, GiveawayWinnerEmailEvent } from 'src/shared/kafka/kafka.service';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import { UserDataDto } from 'src/common/dto/user-data.dto';

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
    private readonly kafkaService: KafkaService, // Kafka producer for email events
    private readonly httpService: HttpService, // HTTP client for fetching user data
  ) {}

  /**
   * Creates a new poll with options inside a session.
   * Uses idempotency key to avoid duplicate poll creation.
   * Uses a database transaction so either all or nothing happens.
   *
   * @param creatorId - User ID who creates the poll.
   * @param sessionId - Session ID where poll belongs.
   * @param dto - Poll details including question and options.
   * @param skipEventRegistrationCheck - If true, skip event registration check (for organizers/admins).
   * @returns The full poll with options and creator info.
   */
  async createPoll(
    creatorId: string,
    sessionId: string,
    dto: CreatePollDto,
    skipEventRegistrationCheck = false,
  ) {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException(
        'Duplicate request. This poll has already been created.',
      );
    }

    // Validate that the user is a participant in this session
    // For organizers/admins, skip the event registration check
    await this.sessionValidationService.validateSessionMembership(
      creatorId,
      sessionId,
      skipEventRegistrationCheck,
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
  async submitVote(userId: string, userEmail: string, dto: SubmitVoteDto) {
    const { pollId, optionId, idempotencyKey } = dto;

    const canProceed =
      await this.idempotencyService.checkAndSet(idempotencyKey);
    if (!canProceed) {
      throw new ConflictException(
        'Duplicate request. This vote has already been submitted.',
      );
    }

    // Ensure user reference exists before creating the vote (foreign key constraint)
    await this.findOrCreateUserReference(userId, userEmail);

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
      // --- HEATMAP TRACKING (uses Pub/Sub, not Streams) ---
      void this.redis.publish(
        'heatmap-events',
        JSON.stringify({ sessionId: pollSessionId, userId }),
      );

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
   * Gets the event name for a given event ID.
   * Attempts to fetch from cache first, then falls back to database.
   */
  private async _getEventName(eventId: string): Promise<string> {
    const cacheKey = `event:name:${eventId}`;
    const cached = await this.redis.get(cacheKey);
    if (cached) return cached;

    // Fallback: Try to get from session which has eventId relation
    // Since we don't have direct event table access, return a generic name
    // The event-lifecycle-service owns the event data
    const eventName = `Event ${eventId.slice(0, 8)}`;
    await this.redis.set(cacheKey, eventName, 'EX', 3600);
    return eventName;
  }

  /**
   * Gets the session name/title for a given session ID.
   */
  private async _getSessionName(sessionId: string): Promise<string> {
    const cacheKey = `session:name:${sessionId}`;
    const cached = await this.redis.get(cacheKey);
    if (cached) return cached;

    const session = await this.prisma.chatSession.findUnique({
      where: { id: sessionId },
      select: { name: true },
    });

    const sessionName = session?.name || `Session ${sessionId.slice(0, 8)}`;
    await this.redis.set(cacheKey, sessionName, 'EX', 3600);
    return sessionName;
  }

  /**
   * Selects a random winner from users who voted for a specific poll option.
   * Giveaways can only be run on closed polls to ensure all votes are in.
   * Persists the winner to the database and returns complete winner info.
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
      include: {
        options: true,
      },
    });

    if (!poll) {
      throw new NotFoundException(`Poll with ID ${dto.pollId} not found.`);
    }

    if (poll.isActive) {
      throw new ForbiddenException(
        'Giveaway can only be run on closed polls. Please close the poll first.',
      );
    }

    // Find the winning option text
    const winningOption = poll.options.find(
      (opt) => opt.id === dto.winningOptionId,
    );
    if (!winningOption) {
      throw new NotFoundException(
        `Option with ID ${dto.winningOptionId} not found in poll.`,
      );
    }

    // 1. Get all users who voted for the winning option with full details
    const voters = await this.prisma.pollVote.findMany({
      where: {
        pollId: dto.pollId,
        optionId: dto.winningOptionId,
      },
      include: {
        user: {
          select: {
            id: true,
            email: true,
            firstName: true,
            lastName: true,
          },
        },
      },
    });

    if (voters.length === 0) {
      this.logger.warn(
        `No voters found for option ${dto.winningOptionId} in poll ${dto.pollId}. No winner selected.`,
      );
      return {
        success: false,
        message: 'No eligible voters found for this option.',
        totalEligibleVoters: 0,
      };
    }

    // 2. Select a random winner
    const winnerIndex = Math.floor(Math.random() * voters.length);
    const winnerVote = voters[winnerIndex];
    const winner = winnerVote.user;

    // Get session metadata
    const metadata = await this._getSessionMetadata(poll.sessionId);

    // 3. Get real user data - ALWAYS fetch from user-and-org-service to get accurate data
    let realFirstName: string | null = null;
    let realLastName: string | null = null;
    let realEmail: string | null = null;

    // Helper function to check if an email is a placeholder (contains user ID as prefix or fake domain)
    const isPlaceholderEmail = (email: string | null, userId: string): boolean => {
      if (!email) return true;
      const emailPrefix = email.split('@')[0];
      const domain = email.split('@')[1] || '';
      // Check if email prefix is the user ID or if domain is a placeholder
      return (
        emailPrefix === userId ||
        domain.includes('unknown.local') ||
        domain.includes('placeholder.local')
      );
    };

    // Check if we have placeholder values that need refreshing
    const hasPlaceholderValues =
      winner.firstName === 'Guest' ||
      winner.lastName === 'User' ||
      isPlaceholderEmail(winner.email, winner.id);

    // Always try to fetch real user data from user-and-org-service
    try {
      const userOrgServiceUrl =
        process.env.USER_ORG_SERVICE_URL || 'http://user-and-org-service:3001';
      const response = await firstValueFrom(
        this.httpService.get<UserDataDto>(
          `${userOrgServiceUrl}/internal/users/${winner.id}`,
          {
            headers: { 'X-Internal-Api-Key': process.env.INTERNAL_API_KEY },
          },
        ),
      );

      const userData = response.data;
      realFirstName = userData.first_name || null;
      realLastName = userData.last_name || null;
      realEmail = userData.email || null;

      // Update the UserReference with real data for future use
      if (hasPlaceholderValues && userData.email) {
        await this.prisma.userReference.update({
          where: { id: winner.id },
          data: {
            email: userData.email,
            firstName: userData.first_name,
            lastName: userData.last_name,
          },
        });
      }

      this.logger.log(
        `Fetched real user data for winner ${winner.id}: ${userData.first_name} ${userData.last_name} (${userData.email})`,
      );
    } catch (error) {
      this.logger.warn(
        `Could not fetch real user data for ${winner.id}: ${error instanceof Error ? error.message : 'Unknown error'}`,
      );
      // If we can't fetch and original data is not placeholder, use it
      if (!hasPlaceholderValues) {
        realFirstName = winner.firstName;
        realLastName = winner.lastName;
        realEmail = winner.email;
      }
      // If placeholder, realFirstName/realLastName/realEmail stay null
    }

    // Build display name with priority: real name > email prefix > fallback
    let winnerName: string;
    if (realFirstName || realLastName) {
      winnerName = [realFirstName, realLastName].filter(Boolean).join(' ');
    } else if (realEmail && !isPlaceholderEmail(realEmail, winner.id)) {
      // Only use email prefix if it's a real email, not a placeholder
      winnerName = realEmail.split('@')[0];
    } else {
      winnerName = 'Winner'; // Final fallback - no real data available
    }

    // 4. Calculate claim deadline if provided
    const claimDeadline = dto.prize?.claimDeadlineHours
      ? new Date(Date.now() + dto.prize.claimDeadlineHours * 60 * 60 * 1000)
      : null;

    // 5. Persist the winner to database
    const giveawayWinner = await this.prisma.giveawayWinner.create({
      data: {
        sessionId: poll.sessionId,
        eventId: metadata.eventId,
        pollId: dto.pollId,
        userId: winner.id,
        winnerName,
        winnerEmail: winner.email,
        giveawayType: 'SINGLE_POLL',
        winningOptionText: winningOption.text,
        prizeTitle: dto.prize?.title,
        prizeDescription: dto.prize?.description,
        prizeType: dto.prize?.type,
        prizeValue: dto.prize?.value,
        claimInstructions: dto.prize?.claimInstructions,
        claimLocation: dto.prize?.claimLocation,
        claimDeadline,
        createdById: adminId,
      },
    });

    // 6. Publish an audit event
    const auditPayload: AuditLogPayload = {
      action: 'GIVEAWAY_WINNER_SELECTED',
      actingUserId: adminId,
      organizationId: metadata.organizationId,
      sessionId: poll.sessionId,
      details: {
        pollId: dto.pollId,
        winningOptionId: dto.winningOptionId,
        winnerId: winner.id,
        winnerEmail: winner.email,
        giveawayWinnerId: giveawayWinner.id,
      },
    };
    void this._publishAuditEvent(auditPayload);

    this.logger.log(
      `User ${winner.id} (${winner.email}) selected as giveaway winner for poll ${dto.pollId}`,
    );

    // 7. Send email notification via Kafka
    const emailEvent: GiveawayWinnerEmailEvent = {
      type: 'GIVEAWAY_WINNER_SINGLE_POLL',
      giveawayWinnerId: giveawayWinner.id,
      winnerEmail: winner.email,
      winnerName,
      eventId: metadata.eventId,
      eventName: await this._getEventName(metadata.eventId),
      sessionId: poll.sessionId,
      sessionName: await this._getSessionName(poll.sessionId),
      prizeTitle: dto.prize?.title,
      prizeDescription: dto.prize?.description,
      claimInstructions: dto.prize?.claimInstructions,
      claimLocation: dto.prize?.claimLocation,
      claimDeadline: claimDeadline?.toISOString(),
      winningOptionText: winningOption.text,
    };

    const emailSent = await this.kafkaService.sendGiveawayWinnerEmail(emailEvent);

    // Update emailSent status in database
    if (emailSent) {
      await this.prisma.giveawayWinner.update({
        where: { id: giveawayWinner.id },
        data: { emailSent: true },
      });
    }

    // 8. Return complete winner info for frontend display
    return {
      success: true,
      giveawayWinnerId: giveawayWinner.id,
      pollId: dto.pollId,
      winner: {
        id: winner.id,
        name: winnerName,
        email: realEmail, // Real email from user-and-org-service
        firstName: realFirstName,
        lastName: realLastName,
        optionText: winningOption.text,
      },
      prize: dto.prize
        ? {
            title: dto.prize.title,
            description: dto.prize.description,
            type: dto.prize.type,
            value: dto.prize.value,
            claimInstructions: dto.prize.claimInstructions,
            claimLocation: dto.prize.claimLocation,
            claimDeadline: claimDeadline?.toISOString(),
          }
        : null,
      totalEligibleVoters: voters.length,
      emailSent,
    };
  }

  // ============================================================
  // QUIZ GIVEAWAY METHODS
  // ============================================================

  /**
   * Configures quiz settings for a session.
   */
  async configureQuizSettings(
    sessionId: string,
    settings: {
      quizEnabled: boolean;
      passingScore: number;
      prize?: {
        title?: string;
        description?: string;
        type?: string;
        value?: number;
        claimInstructions?: string;
        claimLocation?: string;
        claimDeadlineHours?: number;
      };
      maxWinners?: number;
    },
  ) {
    const totalQuestions = await this.prisma.poll.count({
      where: { sessionId, isQuiz: true },
    });

    return this.prisma.sessionQuizSettings.upsert({
      where: { sessionId },
      update: {
        quizEnabled: settings.quizEnabled,
        passingScore: settings.passingScore,
        totalQuestions,
        prizeTitle: settings.prize?.title,
        prizeDescription: settings.prize?.description,
        prizeType: settings.prize?.type,
        prizeValue: settings.prize?.value,
        claimInstructions: settings.prize?.claimInstructions,
        claimLocation: settings.prize?.claimLocation,
        claimDeadlineHours: settings.prize?.claimDeadlineHours ?? 72,
        maxWinners: settings.maxWinners,
      },
      create: {
        sessionId,
        quizEnabled: settings.quizEnabled,
        passingScore: settings.passingScore,
        totalQuestions,
        prizeTitle: settings.prize?.title,
        prizeDescription: settings.prize?.description,
        prizeType: settings.prize?.type,
        prizeValue: settings.prize?.value,
        claimInstructions: settings.prize?.claimInstructions,
        claimLocation: settings.prize?.claimLocation,
        claimDeadlineHours: settings.prize?.claimDeadlineHours ?? 72,
        maxWinners: settings.maxWinners,
      },
    });
  }

  /**
   * Gets quiz settings for a session.
   */
  async getQuizSettings(sessionId: string) {
    return this.prisma.sessionQuizSettings.findUnique({
      where: { sessionId },
    });
  }

  /**
   * Calculates quiz leaderboard for a session.
   */
  async getQuizLeaderboard(sessionId: string, currentUserId?: string): Promise<{
    leaderboard: Array<{ rank: number; userId: string; name: string; score: number; totalQuestions: number; percentage: number; completedAt: string }>;
    totalParticipants: number;
    totalQuestions: number;
    quizComplete: boolean;
    currentUser?: { rank: number; score: number; percentage: number } | null;
  }> {
    const quizPolls = await this.prisma.poll.findMany({
      where: { sessionId, isQuiz: true, correctOptionId: { not: null } },
      select: { id: true, correctOptionId: true },
    });

    if (quizPolls.length === 0) {
      return { leaderboard: [], totalParticipants: 0, totalQuestions: 0, quizComplete: false, currentUser: null };
    }

    const activePolls = await this.prisma.poll.count({
      where: { sessionId, isQuiz: true, isActive: true },
    });
    const quizComplete = activePolls === 0;

    const votes = await this.prisma.pollVote.findMany({
      where: { pollId: { in: quizPolls.map((p) => p.id) } },
      include: {
        user: { select: { id: true, firstName: true, lastName: true, email: true } },
      },
    });

    const userScores = new Map<string, {
      userId: string; name: string; email: string;
      correctAnswers: number; totalAnswered: number; lastAnsweredAt: Date;
    }>();

    for (const vote of votes) {
      const poll = quizPolls.find((p) => p.id === vote.pollId);
      if (!poll) continue;

      const isCorrect = vote.optionId === poll.correctOptionId;

      if (!userScores.has(vote.userId)) {
        userScores.set(vote.userId, {
          userId: vote.userId,
          name: [vote.user.firstName, vote.user.lastName].filter(Boolean).join(' ') || vote.user.email.split('@')[0],
          email: vote.user.email,
          correctAnswers: 0,
          totalAnswered: 0,
          lastAnsweredAt: vote.createdAt,
        });
      }

      const userScore = userScores.get(vote.userId)!;
      userScore.totalAnswered++;
      if (isCorrect) userScore.correctAnswers++;
      if (vote.createdAt > userScore.lastAnsweredAt) userScore.lastAnsweredAt = vote.createdAt;
    }

    const sortedScores = Array.from(userScores.values()).sort((a, b) => {
      if (b.correctAnswers !== a.correctAnswers) return b.correctAnswers - a.correctAnswers;
      return a.lastAnsweredAt.getTime() - b.lastAnsweredAt.getTime();
    });

    const leaderboard = sortedScores.map((score, index) => ({
      rank: index + 1,
      userId: score.userId,
      name: score.name,
      score: score.correctAnswers,
      totalQuestions: quizPolls.length,
      percentage: Math.round((score.correctAnswers / quizPolls.length) * 100),
      completedAt: score.lastAnsweredAt.toISOString(),
    }));

    let currentUserData: { rank: number; score: number; percentage: number } | null = null;
    if (currentUserId) {
      const userEntry = leaderboard.find((e) => e.userId === currentUserId);
      if (userEntry) currentUserData = { rank: userEntry.rank, score: userEntry.score, percentage: userEntry.percentage };
    }

    return { leaderboard: leaderboard.slice(0, 100), totalParticipants: leaderboard.length, totalQuestions: quizPolls.length, quizComplete, currentUser: currentUserData };
  }

  /**
   * Runs a quiz giveaway, selecting winners based on their scores.
   */
  async runQuizGiveaway(sessionId: string, adminId: string, idempotencyKey: string) {
    const canProceed = await this.idempotencyService.checkAndSet(idempotencyKey);
    if (!canProceed) throw new ConflictException('Duplicate request. Quiz giveaway already processed.');

    const quizSettings = await this.prisma.sessionQuizSettings.findUnique({ where: { sessionId } });
    if (!quizSettings || !quizSettings.quizEnabled) {
      throw new ForbiddenException('Quiz giveaway is not enabled for this session.');
    }

    const metadata = await this._getSessionMetadata(sessionId);
    const leaderboardData = await this.getQuizLeaderboard(sessionId);

    if (!leaderboardData.quizComplete) {
      throw new ForbiddenException('Cannot run quiz giveaway while polls are still active.');
    }

    let qualifyingWinners = leaderboardData.leaderboard.filter((e) => e.score >= quizSettings.passingScore);
    if (quizSettings.maxWinners && quizSettings.maxWinners > 0) {
      qualifyingWinners = qualifyingWinners.slice(0, quizSettings.maxWinners);
    }

    const scoreDistribution: Record<number, number> = {};
    for (const entry of leaderboardData.leaderboard) {
      scoreDistribution[entry.score] = (scoreDistribution[entry.score] || 0) + 1;
    }

    const claimDeadline = new Date(Date.now() + (quizSettings.claimDeadlineHours ?? 72) * 60 * 60 * 1000);

    // Get event and session names for emails
    const eventName = await this._getEventName(metadata.eventId);
    const sessionName = await this._getSessionName(sessionId);

    const winnerRecords = await Promise.all(
      qualifyingWinners.map(async (winner) => {
        const user = await this.prisma.userReference.findUnique({ where: { id: winner.userId }, select: { email: true } });
        const winnerEmail = user?.email || 'unknown';

        const record = await this.prisma.giveawayWinner.create({
          data: {
            sessionId, eventId: metadata.eventId, pollId: null,
            userId: winner.userId, winnerName: winner.name, winnerEmail,
            giveawayType: 'QUIZ_SCORE', quizScore: winner.score, quizTotal: leaderboardData.totalQuestions,
            prizeTitle: quizSettings.prizeTitle, prizeDescription: quizSettings.prizeDescription,
            prizeType: quizSettings.prizeType, prizeValue: quizSettings.prizeValue,
            claimInstructions: quizSettings.claimInstructions, claimLocation: quizSettings.claimLocation,
            claimDeadline, createdById: adminId,
          },
        });

        // Send email notification via Kafka
        if (winnerEmail !== 'unknown') {
          const emailEvent: GiveawayWinnerEmailEvent = {
            type: 'GIVEAWAY_WINNER_QUIZ',
            giveawayWinnerId: record.id,
            winnerEmail,
            winnerName: winner.name,
            eventId: metadata.eventId,
            eventName,
            sessionId,
            sessionName,
            prizeTitle: quizSettings.prizeTitle ?? undefined,
            prizeDescription: quizSettings.prizeDescription ?? undefined,
            claimInstructions: quizSettings.claimInstructions ?? undefined,
            claimLocation: quizSettings.claimLocation ?? undefined,
            claimDeadline: claimDeadline.toISOString(),
            quizScore: winner.score,
            quizTotal: leaderboardData.totalQuestions,
          };

          const emailSent = await this.kafkaService.sendGiveawayWinnerEmail(emailEvent);
          if (emailSent) {
            await this.prisma.giveawayWinner.update({
              where: { id: record.id },
              data: { emailSent: true },
            });
          }
        }

        return record;
      }),
    );

    const auditPayload: AuditLogPayload = {
      action: 'QUIZ_GIVEAWAY_COMPLETED', actingUserId: adminId, organizationId: metadata.organizationId, sessionId,
      details: { totalWinners: winnerRecords.length, passingScore: quizSettings.passingScore, totalParticipants: leaderboardData.totalParticipants },
    };
    void this._publishAuditEvent(auditPayload);

    this.logger.log(`Quiz giveaway completed for session ${sessionId}: ${winnerRecords.length} winners`);

    return {
      success: true,
      quizStats: { totalPolls: leaderboardData.totalQuestions, totalParticipants: leaderboardData.totalParticipants, passingScore: quizSettings.passingScore, scoreDistribution },
      winners: qualifyingWinners.map((w) => ({ id: winnerRecords.find((r) => r.userId === w.userId)?.id, name: w.name, score: w.score, totalQuestions: leaderboardData.totalQuestions, percentage: w.percentage })),
      totalWinners: winnerRecords.length,
      prize: { title: quizSettings.prizeTitle, description: quizSettings.prizeDescription, type: quizSettings.prizeType, claimInstructions: quizSettings.claimInstructions, claimLocation: quizSettings.claimLocation, claimDeadline: claimDeadline.toISOString() },
    };
  }

  // ============================================================
  // GIVEAWAY MANAGEMENT METHODS
  // ============================================================

  /**
   * Gets all giveaway winners for a session.
   */
  async getSessionGiveawayWinners(sessionId: string) {
    return this.prisma.giveawayWinner.findMany({ where: { sessionId }, orderBy: { createdAt: 'desc' } });
  }

  /**
   * Gets all giveaway winners for an event.
   */
  async getEventGiveawayWinners(eventId: string) {
    return this.prisma.giveawayWinner.findMany({ where: { eventId }, orderBy: { createdAt: 'desc' } });
  }

  /**
   * Marks a prize as claimed.
   */
  async markPrizeClaimed(winnerId: string) {
    return this.prisma.giveawayWinner.update({
      where: { id: winnerId },
      data: { claimStatus: 'CLAIMED', claimedAt: new Date() },
    });
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

  /**
   * Finds or creates a user reference locally.
   * If the existing record has placeholder values, fetches real data and updates it.
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
