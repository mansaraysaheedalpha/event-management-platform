//src/networking/huddles/huddles.service.ts
import {
  ConflictException,
  ForbiddenException,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { Inject } from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { CreateHuddleDto } from './dto/create-huddle.dto';
import { HuddleResponseType } from './dto/respond-huddle.dto';
import { Prisma, HuddleStatus, HuddleParticipantStatus } from '@prisma/client';
import Redis from 'ioredis';

// Types for service responses
export interface HuddleResponseResult {
  success: boolean;
  error?: string;
  huddleFull?: boolean;
  message?: string;
}

export interface HuddleInvitationPayload {
  huddleId: string;
  topic: string;
  problemStatement: string | null;
  description: string | null;
  locationName: string | null;
  locationDetails: string | null;
  scheduledAt: Date;
  duration: number;
  currentParticipants: number;
  maxParticipants: number;
  confirmedAttendees: Array<{
    userId: string;
    firstName: string | null;
    lastName: string | null;
  }>;
}

export interface HuddleWithParticipants {
  id: string;
  topic: string;
  problemStatement: string | null;
  description: string | null;
  eventId: string;
  sessionId: string | null;
  locationName: string | null;
  locationDetails: string | null;
  scheduledAt: Date;
  duration: number;
  status: HuddleStatus;
  minParticipants: number;
  maxParticipants: number;
  version: number;
  createdById: string | null;
  participants: Array<{
    id: string;
    userId: string;
    status: HuddleParticipantStatus;
  }>;
}

@Injectable()
export class HuddlesService {
  private readonly logger = new Logger(HuddlesService.name);

  // Redis key prefixes
  private readonly HUDDLE_STATS_PREFIX = 'huddle:stats:';
  private readonly HUDDLE_TTL = 86400; // 24 hours

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
  ) {}

  /**
   * Creates a new Huddle and adds the creator as the first participant.
   */
  async createHuddle(
    creatorId: string,
    dto: CreateHuddleDto,
  ): Promise<HuddleWithParticipants> {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException('This huddle has already been created.');
    }

    this.logger.log(
      `User ${creatorId} creating huddle for event ${dto.eventId}`,
    );

    const huddle = await this.prisma.$transaction(async (tx) => {
      // 1. Create the huddle
      const newHuddle = await tx.huddle.create({
        data: {
          topic: dto.topic,
          problemStatement: dto.problemStatement,
          description: dto.description,
          eventId: dto.eventId,
          sessionId: dto.sessionId,
          locationName: dto.locationName,
          locationDetails: dto.locationDetails,
          scheduledAt: new Date(dto.scheduledAt),
          duration: dto.duration ?? 15,
          huddleType: dto.huddleType ?? 'PROBLEM_BASED',
          minParticipants: dto.minParticipants ?? 2,
          maxParticipants: dto.maxParticipants ?? 6,
          createdById: creatorId,
        },
      });

      // 2. Add the creator as the first accepted participant
      await tx.huddleParticipant.create({
        data: {
          huddleId: newHuddle.id,
          userId: creatorId,
          status: 'ACCEPTED',
          respondedAt: new Date(),
        },
      });

      return newHuddle;
    });

    // Cache initial stats in Redis
    await this.updateHuddleCache(huddle.id, 1);

    return this.getHuddle(huddle.id);
  }

  /**
   * Gets a huddle with all its participants.
   */
  async getHuddle(huddleId: string): Promise<HuddleWithParticipants> {
    const huddle = await this.prisma.huddle.findUnique({
      where: { id: huddleId },
      include: {
        participants: {
          select: {
            id: true,
            userId: true,
            status: true,
          },
        },
      },
    });

    if (!huddle) {
      throw new NotFoundException(`Huddle with ID ${huddleId} not found.`);
    }

    return huddle;
  }

  /**
   * Gets a participant record for a user in a huddle.
   */
  async getParticipant(huddleId: string, userId: string) {
    return this.prisma.huddleParticipant.findUnique({
      where: { huddleId_userId: { huddleId, userId } },
    });
  }

  /**
   * Invite users to a huddle.
   * Only participants who are already part of the huddle can invite others.
   */
  async inviteToHuddle(
    inviterId: string,
    huddleId: string,
    userIds: string[],
  ): Promise<{ invited: string[]; alreadyInvited: string[] }> {
    // Verify inviter is a participant
    const inviterParticipant = await this.getParticipant(huddleId, inviterId);
    if (!inviterParticipant || inviterParticipant.status === 'DECLINED') {
      throw new ForbiddenException('You are not a participant in this huddle.');
    }

    const huddle = await this.getHuddle(huddleId);
    if (huddle.status === 'CANCELLED' || huddle.status === 'COMPLETED') {
      throw new ConflictException('This huddle is no longer active.');
    }

    const invited: string[] = [];
    const alreadyInvited: string[] = [];

    for (const userId of userIds) {
      try {
        await this.prisma.huddleParticipant.create({
          data: {
            huddleId,
            userId,
            status: 'INVITED',
          },
        });
        invited.push(userId);
        this.logger.log(`User ${userId} invited to huddle ${huddleId}`);
      } catch (error) {
        if (
          error instanceof Prisma.PrismaClientKnownRequestError &&
          error.code === 'P2002'
        ) {
          // User is already invited
          alreadyInvited.push(userId);
        } else {
          throw error;
        }
      }
    }

    return { invited, alreadyInvited };
  }

  /**
   * Record huddle response with optimistic locking.
   * Prevents overselling spots when multiple users accept simultaneously.
   * @param retryCount - Internal counter for retry attempts (max 3)
   */
  async recordResponse(
    huddleId: string,
    userId: string,
    response: HuddleResponseType,
    retryCount = 0,
  ): Promise<HuddleResponseResult> {
    const MAX_RETRIES = 3;

    // Handle decline - simple case, no race condition concern
    if (response === HuddleResponseType.DECLINE) {
      await this.prisma.huddleParticipant.update({
        where: { huddleId_userId: { huddleId, userId } },
        data: {
          status: 'DECLINED',
          respondedAt: new Date(),
        },
      });
      this.logger.log(`User ${userId} declined huddle ${huddleId}`);
      return { success: true };
    }

    // Handle accept - use optimistic locking to prevent overselling
    try {
      return await this.prisma.$transaction(async (tx) => {
        // Step 1: Get current huddle state
        const huddle = await tx.huddle.findUnique({
          where: { id: huddleId },
          include: {
            participants: {
              where: { status: 'ACCEPTED' },
            },
          },
        });

        if (!huddle) {
          return { success: false, error: 'Huddle not found' };
        }

        if (huddle.status === 'CANCELLED') {
          return { success: false, error: 'This huddle has been cancelled' };
        }

        if (huddle.status === 'COMPLETED') {
          return { success: false, error: 'This huddle has already ended' };
        }

        // Step 2: Check if there's room
        const currentCount = huddle.participants.length;
        if (currentCount >= huddle.maxParticipants) {
          return {
            success: false,
            huddleFull: true,
            error: 'Huddle is full',
            message:
              'This huddle is now full. Try another huddle or create your own!',
          };
        }

        // Step 3: Optimistic lock check and version increment
        const updateResult = await tx.huddle.updateMany({
          where: {
            id: huddleId,
            version: huddle.version, // Optimistic lock check
          },
          data: {
            version: { increment: 1 },
          },
        });

        // If no rows updated, another transaction got there first
        if (updateResult.count === 0) {
          // Retry - huddle was modified
          throw new Error('RETRY_TRANSACTION');
        }

        // Step 4: Update participant status
        await tx.huddleParticipant.update({
          where: { huddleId_userId: { huddleId, userId } },
          data: {
            status: 'ACCEPTED',
            respondedAt: new Date(),
          },
        });

        this.logger.log(`User ${userId} accepted huddle ${huddleId}`);
        return { success: true };
      });
    } catch (error) {
      if (error instanceof Error && error.message === 'RETRY_TRANSACTION') {
        if (retryCount >= MAX_RETRIES) {
          this.logger.error(
            `Max retries exceeded for user ${userId} on huddle ${huddleId}`,
          );
          return {
            success: false,
            error: 'Unable to process request due to high demand. Please try again.',
          };
        }
        this.logger.warn(
          `Retrying accept for user ${userId} on huddle ${huddleId} (attempt ${retryCount + 1}/${MAX_RETRIES})`,
        );
        return this.recordResponse(huddleId, userId, response, retryCount + 1);
      }
      throw error;
    }
  }

  /**
   * Check and confirm huddle when minimum participants reached.
   */
  async checkAndConfirmHuddle(huddleId: string): Promise<boolean> {
    const result = await this.prisma.$transaction(async (tx) => {
      const huddle = await tx.huddle.findUnique({
        where: { id: huddleId },
        include: {
          participants: {
            where: { status: 'ACCEPTED' },
          },
        },
      });

      if (!huddle || huddle.status !== 'FORMING') {
        return false;
      }

      const acceptedCount = huddle.participants.length;
      const minRequired = huddle.minParticipants;

      if (acceptedCount >= minRequired) {
        await tx.huddle.update({
          where: { id: huddleId },
          data: { status: 'CONFIRMED' },
        });
        this.logger.log(
          `Huddle ${huddleId} confirmed with ${acceptedCount} participants`,
        );
        return true;
      }

      return false;
    });

    // Update cache after confirmation
    if (result) {
      const huddle = await this.getHuddle(huddleId);
      const acceptedCount = huddle.participants.filter(
        (p) => p.status === 'ACCEPTED',
      ).length;
      await this.updateHuddleCache(huddleId, acceptedCount);
    }

    return result;
  }

  /**
   * User leaves a huddle they previously joined.
   */
  async leaveHuddle(huddleId: string, userId: string): Promise<void> {
    const participant = await this.getParticipant(huddleId, userId);
    if (!participant) {
      throw new NotFoundException('You are not a participant in this huddle.');
    }

    const huddle = await this.getHuddle(huddleId);

    // Can only leave if huddle hasn't started yet
    if (huddle.status === 'IN_PROGRESS') {
      throw new ConflictException('Cannot leave a huddle that is in progress.');
    }

    if (huddle.status === 'COMPLETED') {
      throw new ConflictException(
        'Cannot leave a huddle that has already ended.',
      );
    }

    await this.prisma.huddleParticipant.update({
      where: { huddleId_userId: { huddleId, userId } },
      data: {
        status: 'DECLINED',
        respondedAt: new Date(),
      },
    });

    // Update cache
    const acceptedCount = huddle.participants.filter(
      (p) => p.status === 'ACCEPTED' && p.userId !== userId,
    ).length;
    await this.updateHuddleCache(huddleId, acceptedCount);

    this.logger.log(`User ${userId} left huddle ${huddleId}`);
  }

  /**
   * Mark a huddle as started (in progress).
   */
  async startHuddle(huddleId: string, userId: string): Promise<void> {
    const huddle = await this.getHuddle(huddleId);

    // Only the creator or an admin can start the huddle
    if (huddle.createdById !== userId) {
      throw new ForbiddenException('Only the huddle creator can start it.');
    }

    if (huddle.status !== 'CONFIRMED') {
      throw new ConflictException(
        'Huddle must be confirmed before it can start.',
      );
    }

    await this.prisma.huddle.update({
      where: { id: huddleId },
      data: { status: 'IN_PROGRESS' },
    });

    this.logger.log(`Huddle ${huddleId} started`);
  }

  /**
   * Mark a huddle as completed.
   */
  async completeHuddle(huddleId: string, userId: string): Promise<void> {
    const huddle = await this.getHuddle(huddleId);

    // Only the creator can complete the huddle
    if (huddle.createdById !== userId) {
      throw new ForbiddenException('Only the huddle creator can complete it.');
    }

    if (huddle.status !== 'IN_PROGRESS') {
      throw new ConflictException('Huddle must be in progress to complete.');
    }

    await this.prisma.huddle.update({
      where: { id: huddleId },
      data: { status: 'COMPLETED' },
    });

    this.logger.log(`Huddle ${huddleId} completed`);
  }

  /**
   * Cancel a huddle.
   */
  async cancelHuddle(
    huddleId: string,
    userId: string,
    reason?: string,
  ): Promise<void> {
    const huddle = await this.getHuddle(huddleId);

    // Only the creator can cancel
    if (huddle.createdById !== userId) {
      throw new ForbiddenException('Only the huddle creator can cancel it.');
    }

    if (
      huddle.status === 'COMPLETED' ||
      huddle.status === 'CANCELLED'
    ) {
      throw new ConflictException('Huddle cannot be cancelled.');
    }

    await this.prisma.huddle.update({
      where: { id: huddleId },
      data: { status: 'CANCELLED' },
    });

    // Clear cache
    await this.redis.del(`${this.HUDDLE_STATS_PREFIX}${huddleId}`);

    this.logger.log(`Huddle ${huddleId} cancelled. Reason: ${reason}`);
  }

  /**
   * Get active huddles for an event.
   */
  async getActiveHuddles(eventId: string): Promise<HuddleWithParticipants[]> {
    return this.prisma.huddle.findMany({
      where: {
        eventId,
        status: {
          in: ['FORMING', 'CONFIRMED'],
        },
        scheduledAt: {
          gte: new Date(), // Only future huddles
        },
      },
      include: {
        participants: {
          select: {
            id: true,
            userId: true,
            status: true,
          },
        },
      },
      orderBy: {
        scheduledAt: 'asc',
      },
    });
  }

  /**
   * Get huddles for a user.
   */
  async getUserHuddles(userId: string, eventId?: string) {
    const where: Prisma.HuddleParticipantWhereInput = {
      userId,
      status: { in: ['INVITED', 'ACCEPTED'] },
    };

    if (eventId) {
      where.huddle = { eventId };
    }

    return this.prisma.huddleParticipant.findMany({
      where,
      include: {
        huddle: {
          include: {
            participants: {
              where: { status: 'ACCEPTED' },
              select: {
                userId: true,
              },
            },
          },
        },
      },
      orderBy: {
        huddle: {
          scheduledAt: 'asc',
        },
      },
    });
  }

  /**
   * Get quick stats from Redis cache.
   */
  async getHuddleQuickStats(huddleId: string): Promise<{ participantCount: number } | null> {
    const cached = await this.redis.hgetall(
      `${this.HUDDLE_STATS_PREFIX}${huddleId}`,
    );

    if (cached && cached.participantCount) {
      return {
        participantCount: parseInt(cached.participantCount, 10),
      };
    }

    // Cache miss - compute and cache
    const huddle = await this.getHuddle(huddleId);
    const acceptedCount = huddle.participants.filter(
      (p) => p.status === 'ACCEPTED',
    ).length;
    await this.updateHuddleCache(huddleId, acceptedCount);

    return { participantCount: acceptedCount };
  }

  /**
   * Update huddle participant count in Redis cache.
   */
  private async updateHuddleCache(
    huddleId: string,
    participantCount: number,
  ): Promise<void> {
    const key = `${this.HUDDLE_STATS_PREFIX}${huddleId}`;
    await this.redis.hset(key, 'participantCount', participantCount.toString());
    await this.redis.expire(key, this.HUDDLE_TTL);
  }

  /**
   * Build invitation payload for WebSocket emission.
   */
  async buildInvitationPayload(huddleId: string): Promise<HuddleInvitationPayload> {
    const huddle = await this.prisma.huddle.findUnique({
      where: { id: huddleId },
      include: {
        participants: {
          where: { status: 'ACCEPTED' },
          select: {
            userId: true,
          },
        },
      },
    });

    if (!huddle) {
      throw new NotFoundException(`Huddle ${huddleId} not found`);
    }

    // Get user details for confirmed attendees
    const userIds = huddle.participants.map((p) => p.userId);
    const users = await this.prisma.userReference.findMany({
      where: { id: { in: userIds } },
      select: { id: true, firstName: true, lastName: true },
    });

    return {
      huddleId: huddle.id,
      topic: huddle.topic,
      problemStatement: huddle.problemStatement,
      description: huddle.description,
      locationName: huddle.locationName,
      locationDetails: huddle.locationDetails,
      scheduledAt: huddle.scheduledAt,
      duration: huddle.duration,
      currentParticipants: huddle.participants.length,
      maxParticipants: huddle.maxParticipants,
      confirmedAttendees: users.map((u) => ({
        userId: u.id,
        firstName: u.firstName,
        lastName: u.lastName,
      })),
    };
  }
}
