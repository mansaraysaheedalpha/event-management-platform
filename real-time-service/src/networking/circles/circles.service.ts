import {
  ConflictException,
  ForbiddenException,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { CreateCircleDto } from './dto/create-circle.dto';
import { Prisma } from '@prisma/client';

@Injectable()
export class CirclesService {
  private readonly logger = new Logger(CirclesService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
  ) {}

  /**
   * Creates a new Conversation Circle and adds the creator as the first participant.
   */
  async createCircle(
    creatorId: string,
    sessionId: string,
    dto: CreateCircleDto,
  ) {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException(
        'This conversation circle has already been created.',
      );
    }

    this.logger.log(
      `User ${creatorId} creating circle in session ${sessionId}`,
    );

    // Use a transaction to ensure both the circle and the initial participant are created together
    const newCircle = await this.prisma.$transaction(async (tx) => {
      // 1. Create the circle
      const circle = await tx.conversationCircle.create({
        data: {
          topic: dto.topic,
          creatorId,
          sessionId,
        },
      });

      // 2. Add the creator as the first participant
      await tx.conversationCircleParticipant.create({
        data: {
          userId: creatorId,
          circleId: circle.id,
        },
      });

      return circle;
    });

    // Fetch the full circle with its creator details to be broadcasted
    return this.prisma.conversationCircle.findUnique({
      where: { id: newCircle.id },
      include: {
        creator: {
          select: { id: true, firstName: true, lastName: true },
        },
      },
    });
  }

  /**
   * Adds a user to a Conversation Circle.
   */
  async joinCircle(userId: string, circleId: string) {
    // The `create` will fail with a unique constraint error if the user
    // is already a participant, which is a safe way to handle this.
    try {
      await this.prisma.conversationCircleParticipant.create({
        data: {
          userId,
          circleId,
        },
      });
      this.logger.log(`User ${userId} joined circle ${circleId}`);
    } catch (error) {
      if (
        error instanceof Prisma.PrismaClientKnownRequestError &&
        error.code === 'P2002'
      ) {
        throw new ConflictException('You are already in this circle.');
      }
      throw error;
    }
    return this._getCircleRoster(circleId);
  }

  /**
   * Removes a user from a Conversation Circle.
   */
  async leaveCircle(userId: string, circleId: string) {
    await this.prisma.conversationCircleParticipant.delete({
      where: {
        userId_circleId: {
          userId,
          circleId,
        },
      },
    });
    this.logger.log(`User ${userId} left circle ${circleId}`);
    return this._getCircleRoster(circleId);
  }

  /**
   * Private helper to get the current list of participants for a circle.
   */
  private async _getCircleRoster(circleId: string) {
    return this.prisma.conversationCircle.findUnique({
      where: { id: circleId },
      select: {
        id: true,
        participants: {
          select: {
            user: {
              select: {
                id: true,
                firstName: true,
                lastName: true,
              },
            },
          },
        },
      },
    });
  }

  /**
   * Closes a Conversation Circle.
   * This is a protected action for the circle creator or an admin.
   */
  async closeCircle(
    circleId: string,
    adminId: string,
    adminPermissions: string[],
  ) {
    const circle = await this.prisma.conversationCircle.findUnique({
      where: { id: circleId },
      select: { creatorId: true },
    });

    if (!circle) {
      throw new NotFoundException(
        `Conversation Circle with ID ${circleId} not found.`,
      );
    }

    const isCreator = circle.creatorId === adminId;
    const hasModeratorPermission = adminPermissions.includes('circles:manage'); // A new, specific permission

    // The user can proceed if they are the creator OR have the override permission.
    if (!isCreator && !hasModeratorPermission) {
      throw new ForbiddenException(
        'You do not have permission to close this circle.',
      );
    }

    const closedCircle = await this.prisma.conversationCircle.update({
      where: { id: circleId },
      data: { isActive: false },
    });

    this.logger.log(`Circle ${closedCircle.id} was closed by admin ${adminId}`);
    return closedCircle;
  }
}
