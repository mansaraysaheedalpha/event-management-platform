// src/gamification/teams/team-chat/team-chat.service.ts
import {
  ForbiddenException,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';

@Injectable()
export class TeamChatService {
  private readonly logger = new Logger(TeamChatService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
  ) {}

  /**
   * Verifies the user is a member of the specified team.
   * Throws ForbiddenException if not.
   */
  async assertTeamMembership(userId: string, teamId: string) {
    const membership = await this.prisma.teamMembership.findFirst({
      where: { userId, teamId },
      select: { id: true },
    });
    if (!membership) {
      throw new ForbiddenException(
        'You must be a member of this team to use team chat.',
      );
    }
  }

  /**
   * Sends a message to the team chat. Idempotent via idempotency key.
   */
  async sendMessage(
    authorId: string,
    teamId: string,
    text: string,
    idempotencyKey: string,
    metadata?: Record<string, any>,
  ) {
    const canProceed =
      await this.idempotencyService.checkAndSet(idempotencyKey);
    if (!canProceed) {
      // Already processed — return the existing message
      const existing = await this.prisma.teamMessage.findFirst({
        where: { teamId, authorId },
        orderBy: { createdAt: 'desc' },
        include: {
          author: {
            select: { id: true, firstName: true, lastName: true },
          },
        },
      });
      return existing;
    }

    const message = await this.prisma.teamMessage.create({
      data: {
        teamId,
        authorId,
        text,
        metadata: metadata ?? undefined,
        reactions: {},
      },
      include: {
        author: {
          select: { id: true, firstName: true, lastName: true },
        },
      },
    });

    this.logger.log(
      `Team chat message ${message.id} sent by ${authorId} in team ${teamId}`,
    );
    return message;
  }

  /**
   * Toggles a reaction on a team message. If the user already reacted
   * with this emoji, removes it. Otherwise, adds it.
   *
   * reactions JSON shape: { "emoji": ["userId1", "userId2"] }
   */
  async toggleReaction(
    userId: string,
    teamId: string,
    messageId: string,
    emoji: string,
    idempotencyKey: string,
  ) {
    const canProceed =
      await this.idempotencyService.checkAndSet(idempotencyKey);
    if (!canProceed) {
      return this._getMessageById(messageId);
    }

    const message = await this.prisma.teamMessage.findFirst({
      where: { id: messageId, teamId },
    });
    if (!message) {
      throw new NotFoundException(
        `Message ${messageId} not found in team ${teamId}.`,
      );
    }

    const reactions = (message.reactions as Record<string, string[]>) ?? {};
    const existing = reactions[emoji] ?? [];

    if (existing.includes(userId)) {
      // Remove the user's reaction
      reactions[emoji] = existing.filter((id) => id !== userId);
      if (reactions[emoji].length === 0) delete reactions[emoji];
    } else {
      // Add the user's reaction
      reactions[emoji] = [...existing, userId];
    }

    const updated = await this.prisma.teamMessage.update({
      where: { id: messageId },
      data: { reactions },
      include: {
        author: {
          select: { id: true, firstName: true, lastName: true },
        },
      },
    });

    return updated;
  }

  /**
   * Retrieves paginated chat history for a team.
   * Uses cursor-based pagination (before messageId).
   */
  async getHistory(teamId: string, limit = 50, before?: string) {
    const where: any = { teamId };
    if (before) {
      const cursor = await this.prisma.teamMessage.findUnique({
        where: { id: before },
        select: { createdAt: true },
      });
      if (cursor) {
        where.createdAt = { lt: cursor.createdAt };
      }
    }

    const messages = await this.prisma.teamMessage.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      take: limit,
      include: {
        author: {
          select: { id: true, firstName: true, lastName: true },
        },
      },
    });

    // Return in chronological order (oldest first)
    return messages.reverse();
  }

  private async _getMessageById(messageId: string) {
    return this.prisma.teamMessage.findUnique({
      where: { id: messageId },
      include: {
        author: {
          select: { id: true, firstName: true, lastName: true },
        },
      },
    });
  }
}
