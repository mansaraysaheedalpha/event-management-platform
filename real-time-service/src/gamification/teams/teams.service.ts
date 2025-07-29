import {
  ConflictException,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { CreateTeamDto } from './dto/create-team.dto';

@Injectable()
export class TeamsService {
  private readonly logger = new Logger(TeamsService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
  ) {}

  /**
   * Creates a new Team and adds the creator as the first member.
   */
  async createTeam(creatorId: string, sessionId: string, dto: CreateTeamDto) {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException('This team has already been created.');
    }

    // Use a transaction to ensure both the team and the initial membership are created together
    const newTeam = await this.prisma.$transaction(async (tx) => {
      // 1. Create the Team
      const team = await tx.team.create({
        data: {
          name: dto.name,
          creatorId,
          sessionId,
        },
      });

      // 2. Add the creator as the first member
      await tx.teamMembership.create({
        data: {
          userId: creatorId,
          teamId: team.id,
        },
      });

      return team;
    });

    this.logger.log(
      `User ${creatorId} created new team ${newTeam.id} in session ${sessionId}`,
    );

    // Fetch the full team with its creator details to be broadcasted
    return this.prisma.team.findUnique({
      where: { id: newTeam.id },
      include: {
        creator: {
          select: { id: true, firstName: true, lastName: true },
        },
        // We also want to include the initial member list
        members: {
          include: {
            user: {
              select: { id: true, firstName: true, lastName: true },
            },
          },
        },
      },
    });
  }

  /**
   * Adds a user to a team.
   */
  async joinTeam(userId: string, teamId: string) {
    // A user might be a member of another team in the same session.
    // First, we must ensure they leave any existing team in this session.
    const team = await this.prisma.team.findUnique({
      where: { id: teamId },
      select: { sessionId: true },
    });
    if (!team) {
      throw new NotFoundException(`Team with ID ${teamId} not found.`);
    }

    // This transaction ensures the user leaves their old team and joins the new one atomically.
    await this.prisma.$transaction(async (tx) => {
      // Find if the user is a member of any other team in this session.
      const existingMembership = await tx.teamMembership.findFirst({
        where: {
          userId,
          team: { sessionId: team.sessionId },
        },
      });

      if (existingMembership) {
        // If they are on another team, remove them first.
        await tx.teamMembership.delete({
          where: {
            userId_teamId: { userId, teamId: existingMembership.teamId },
          },
        });
      }

      // Now, create the new membership.
      await tx.teamMembership.create({
        data: { userId, teamId },
      });
    });

    this.logger.log(`User ${userId} joined team ${teamId}`);
    return this._getTeamWithRoster(teamId);
  }

  /**
   * Removes a user from a team.
   */
  async leaveTeam(userId: string, teamId: string) {
    await this.prisma.teamMembership.delete({
      where: {
        userId_teamId: { userId, teamId },
      },
    });

    this.logger.log(`User ${userId} left team ${teamId}`);
    return this._getTeamWithRoster(teamId);
  }

  /**
   * Private helper to get a team with its current list of members.
   */
  private async _getTeamWithRoster(teamId: string) {
    return this.prisma.team.findUnique({
      where: { id: teamId },
      include: {
        members: {
          include: {
            user: {
              select: { id: true, firstName: true, lastName: true },
            },
          },
        },
      },
    });
  }
}
