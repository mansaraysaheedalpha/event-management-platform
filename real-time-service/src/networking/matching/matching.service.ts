//src/networking/matching/matching.service.ts
import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { ContextType } from '@prisma/client';

export interface ConnectionContextItem {
  contextType: ContextType;
  contextValue: string;
}

export interface EnhancedNearbyUser {
  id: string;
  name: string;
  avatarUrl?: string;
  email?: string;
  distance?: number;
  connectionContexts: ConnectionContextItem[];
  matchScore: number;
  alreadyConnected: boolean;
}

@Injectable()
export class MatchingService {
  private readonly logger = new Logger(MatchingService.name);

  constructor(private readonly prisma: PrismaService) {}

  /**
   * Generate connection context for two users at an event.
   * This helps explain WHY two users might want to connect.
   */
  async generateConnectionContext(
    userAId: string,
    userBId: string,
    eventId: string,
  ): Promise<ConnectionContextItem[]> {
    const contexts: ConnectionContextItem[] = [];

    try {
      // 1. Find shared sessions (both participated in same session)
      const sharedSessions = await this.findSharedSessions(userAId, userBId, eventId);
      contexts.push(
        ...sharedSessions.map((sessionName) => ({
          contextType: ContextType.SHARED_SESSION,
          contextValue: sessionName,
        })),
      );

      // 2. Find Q&A interactions (one asked, other upvoted or vice versa)
      const qaInteractions = await this.findQAInteractions(userAId, userBId, eventId);
      contexts.push(...qaInteractions);

      // 3. Find mutual connections (both connected to same third person)
      const mutualConnections = await this.findMutualConnections(userAId, userBId);
      contexts.push(
        ...mutualConnections.map((name) => ({
          contextType: ContextType.MUTUAL_CONNECTION,
          contextValue: name,
        })),
      );
    } catch (error) {
      this.logger.error(
        `Error generating context for ${userAId} and ${userBId}:`,
        error,
      );
    }

    return contexts;
  }

  /**
   * Find sessions where both users participated.
   * Participation is inferred from messages, questions, or poll votes.
   */
  private async findSharedSessions(
    userAId: string,
    userBId: string,
    eventId: string,
  ): Promise<string[]> {
    // Find sessions where userA participated
    const userASessions = await this.getUserEventSessions(userAId, eventId);

    // Find sessions where userB participated
    const userBSessions = await this.getUserEventSessions(userBId, eventId);

    // Find intersection
    const sharedSessionIds = userASessions.filter((id) =>
      userBSessions.includes(id),
    );

    if (sharedSessionIds.length === 0) {
      return [];
    }

    // Get session names
    const sessions = await this.prisma.chatSession.findMany({
      where: { id: { in: sharedSessionIds } },
      select: { name: true },
    });

    return sessions.map((s) => s.name);
  }

  /**
   * Get all sessions a user participated in for an event.
   * Participation = sent message, asked question, or voted in poll.
   */
  private async getUserEventSessions(
    userId: string,
    eventId: string,
  ): Promise<string[]> {
    const sessionIds = new Set<string>();

    // Sessions with messages from user
    const messageSessions = await this.prisma.message.findMany({
      where: {
        authorId: userId,
        session: { eventId },
      },
      select: { sessionId: true },
      distinct: ['sessionId'],
    });
    messageSessions.forEach((m) => sessionIds.add(m.sessionId));

    // Sessions with questions from user
    const questionSessions = await this.prisma.question.findMany({
      where: {
        authorId: userId,
        session: { eventId },
      },
      select: { sessionId: true },
      distinct: ['sessionId'],
    });
    questionSessions.forEach((q) => sessionIds.add(q.sessionId));

    // Sessions with poll votes from user
    const pollVoteSessions = await this.prisma.pollVote.findMany({
      where: {
        userId,
        poll: { session: { eventId } },
      },
      select: { poll: { select: { sessionId: true } } },
    });
    pollVoteSessions.forEach((pv) => sessionIds.add(pv.poll.sessionId));

    return Array.from(sessionIds);
  }

  /**
   * Find Q&A interactions between two users.
   * Example: User A asked a question that User B upvoted.
   */
  private async findQAInteractions(
    userAId: string,
    userBId: string,
    eventId: string,
  ): Promise<ConnectionContextItem[]> {
    const interactions: ConnectionContextItem[] = [];

    // Check if userB upvoted any of userA's questions
    const userAQuestions = await this.prisma.question.findMany({
      where: {
        authorId: userAId,
        session: { eventId },
        upvotes: { some: { userId: userBId } },
      },
      select: { text: true },
      take: 2,
    });

    userAQuestions.forEach((q) => {
      interactions.push({
        contextType: ContextType.QA_INTERACTION,
        contextValue: `Upvoted: "${q.text.substring(0, 50)}${q.text.length > 50 ? '...' : ''}"`,
      });
    });

    // Check if userA upvoted any of userB's questions
    const userBQuestions = await this.prisma.question.findMany({
      where: {
        authorId: userBId,
        session: { eventId },
        upvotes: { some: { userId: userAId } },
      },
      select: { text: true },
      take: 2,
    });

    userBQuestions.forEach((q) => {
      interactions.push({
        contextType: ContextType.QA_INTERACTION,
        contextValue: `Interested in: "${q.text.substring(0, 50)}${q.text.length > 50 ? '...' : ''}"`,
      });
    });

    // Check if one answered the other's question
    const userAAnsweredB = await this.prisma.answer.findFirst({
      where: {
        authorId: userAId,
        question: {
          authorId: userBId,
          session: { eventId },
        },
      },
      select: { question: { select: { text: true } } },
    });

    if (userAAnsweredB) {
      interactions.push({
        contextType: ContextType.QA_INTERACTION,
        contextValue: 'Answered their question',
      });
    }

    const userBAnsweredA = await this.prisma.answer.findFirst({
      where: {
        authorId: userBId,
        question: {
          authorId: userAId,
          session: { eventId },
        },
      },
      select: { question: { select: { text: true } } },
    });

    if (userBAnsweredA) {
      interactions.push({
        contextType: ContextType.QA_INTERACTION,
        contextValue: 'Answered your question',
      });
    }

    return interactions;
  }

  /**
   * Find mutual connections between two users (across all events).
   */
  private async findMutualConnections(
    userAId: string,
    userBId: string,
  ): Promise<string[]> {
    // Get all users connected to userA
    const userAConnections = await this.prisma.connection.findMany({
      where: {
        OR: [{ userAId }, { userBId: userAId }],
      },
      select: {
        userAId: true,
        userBId: true,
        userA: { select: { firstName: true, lastName: true } },
        userB: { select: { firstName: true, lastName: true } },
      },
    });

    const userAConnectedIds = new Set<string>();
    userAConnections.forEach((c) => {
      if (c.userAId === userAId) {
        userAConnectedIds.add(c.userBId);
      } else {
        userAConnectedIds.add(c.userAId);
      }
    });

    // Get all users connected to userB
    const userBConnections = await this.prisma.connection.findMany({
      where: {
        OR: [{ userAId: userBId }, { userBId }],
      },
      select: {
        userAId: true,
        userBId: true,
        userA: { select: { firstName: true, lastName: true } },
        userB: { select: { firstName: true, lastName: true } },
      },
    });

    const mutualNames: string[] = [];
    userBConnections.forEach((c) => {
      const connectedUserId = c.userAId === userBId ? c.userBId : c.userAId;
      if (userAConnectedIds.has(connectedUserId) && connectedUserId !== userAId && connectedUserId !== userBId) {
        const connectedUser = c.userAId === userBId ? c.userB : c.userA;
        const name = `${connectedUser.firstName || ''} ${connectedUser.lastName || ''}`.trim();
        if (name && !mutualNames.includes(name)) {
          mutualNames.push(name);
        }
      }
    });

    return mutualNames.slice(0, 3); // Limit to 3 mutual connections
  }

  /**
   * Calculate a match score based on connection contexts.
   */
  calculateMatchScore(contexts: ConnectionContextItem[]): number {
    let score = 0;

    contexts.forEach((ctx) => {
      switch (ctx.contextType) {
        case ContextType.SHARED_SESSION:
          score += 20; // High value - same session attendance
          break;
        case ContextType.QA_INTERACTION:
          score += 30; // Very high - direct engagement
          break;
        case ContextType.MUTUAL_CONNECTION:
          score += 15; // Medium - network overlap
          break;
        case ContextType.SHARED_INTEREST:
          score += 25; // High - common interests
          break;
        case ContextType.SAME_INDUSTRY:
          score += 10;
          break;
        case ContextType.SAME_COMPANY_SIZE:
          score += 5;
          break;
      }
    });

    // Cap at 100
    return Math.min(score, 100);
  }

  /**
   * Get enhanced nearby users with connection context.
   * Takes a list of nearby user IDs and enriches them with context.
   */
  async getEnhancedNearbyUsers(
    userId: string,
    nearbyUserIds: string[],
    eventId: string,
  ): Promise<EnhancedNearbyUser[]> {
    if (nearbyUserIds.length === 0) {
      return [];
    }

    // Get user details for all nearby users
    const userDetails = await this.prisma.userReference.findMany({
      where: { id: { in: nearbyUserIds } },
      select: {
        id: true,
        firstName: true,
        lastName: true,
        email: true,
        avatarUrl: true,
      },
    });

    // Check existing connections
    const existingConnections = await this.prisma.connection.findMany({
      where: {
        eventId,
        OR: nearbyUserIds.flatMap((nearbyId) => [
          { userAId: userId, userBId: nearbyId },
          { userAId: nearbyId, userBId: userId },
        ]),
      },
      select: { userAId: true, userBId: true },
    });

    const connectedUserIds = new Set<string>();
    existingConnections.forEach((c) => {
      connectedUserIds.add(c.userAId === userId ? c.userBId : c.userAId);
    });

    // Generate context for each nearby user
    const enhancedUsers = await Promise.all(
      userDetails.map(async (nearbyUser) => {
        const contexts = await this.generateConnectionContext(
          userId,
          nearbyUser.id,
          eventId,
        );

        const name = `${nearbyUser.firstName || ''} ${nearbyUser.lastName || ''}`.trim() || 'Attendee';

        return {
          id: nearbyUser.id,
          name,
          avatarUrl: nearbyUser.avatarUrl || undefined,
          email: nearbyUser.email,
          connectionContexts: contexts,
          matchScore: this.calculateMatchScore(contexts),
          alreadyConnected: connectedUserIds.has(nearbyUser.id),
        };
      }),
    );

    // Sort by match score (highest first), then by already connected (not connected first)
    return enhancedUsers.sort((a, b) => {
      if (a.alreadyConnected !== b.alreadyConnected) {
        return a.alreadyConnected ? 1 : -1; // Not connected first
      }
      return b.matchScore - a.matchScore; // Higher score first
    });
  }

  /**
   * Store connection contexts when a connection is created.
   */
  async storeConnectionContexts(
    connectionId: string,
    contexts: ConnectionContextItem[],
  ): Promise<void> {
    if (contexts.length === 0) return;

    await this.prisma.connectionContext.createMany({
      data: contexts.map((ctx) => ({
        connectionId,
        contextType: ctx.contextType,
        contextValue: ctx.contextValue,
      })),
    });
  }
}
