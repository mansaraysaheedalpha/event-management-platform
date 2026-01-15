//src/networking/connections/connections.service.ts
import { Injectable, Logger, NotFoundException } from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { CreateConnectionDto, ReportOutcomeDto } from './dto';
import {
  Connection,
  ConnectionType,
  ConnectionStrength,
  ConnectionActivityType,
  Prisma,
} from '@prisma/client';

export interface ConnectionWithContext extends Connection {
  userA: {
    id: string;
    firstName: string | null;
    lastName: string | null;
    email: string;
    avatarUrl: string | null;
  };
  userB: {
    id: string;
    firstName: string | null;
    lastName: string | null;
    email: string;
    avatarUrl: string | null;
  };
  contexts: {
    id: string;
    contextType: string;
    contextValue: string;
  }[];
  activities?: {
    id: string;
    createdAt: Date;
    activityType: ConnectionActivityType;
    description: string | null;
    metadata: Prisma.JsonValue | null;
    initiatorId: string | null;
  }[];
}

export interface LogActivityParams {
  connectionId: string;
  activityType: ConnectionActivityType;
  initiatorId?: string;
  description?: string;
  metadata?: Record<string, unknown>;
}

// Strength calculation thresholds
const STRENGTH_THRESHOLDS = {
  MODERATE_MIN_INTERACTIONS: 2,
  STRONG_MIN_INTERACTIONS: 4,
  STRONG_ACTIVITY_TYPES: [
    ConnectionActivityType.FOLLOW_UP_REPLIED,
    ConnectionActivityType.MEETING_SCHEDULED,
    ConnectionActivityType.MEETING_HELD,
    ConnectionActivityType.OUTCOME_REPORTED,
  ] as ConnectionActivityType[],
  MODERATE_ACTIVITY_TYPES: [
    ConnectionActivityType.FOLLOW_UP_SENT,
    ConnectionActivityType.FOLLOW_UP_OPENED,
    ConnectionActivityType.DM_SENT,
    ConnectionActivityType.HUDDLE_TOGETHER,
    ConnectionActivityType.LINKEDIN_CONNECTED,
  ] as ConnectionActivityType[],
};

export interface EventNetworkingStats {
  totalConnections: number;
  uniqueNetworkers: number;
  followUpsSent: number;
  followUpRate: number;
  meetingsScheduled: number;
  reportedOutcomes: number;
  connectionsByType: Record<string, number>;
  topConnectors: Array<{
    userId: string;
    name: string;
    connectionCount: number;
  }>;
}

export interface UserNetworkingStats {
  totalConnections: number;
  eventCount: number;
  followUpRate: number;
  outcomeRate: number;
  connectionsByEvent: Array<{
    eventId: string;
    count: number;
  }>;
}

@Injectable()
export class ConnectionsService {
  private readonly logger = new Logger(ConnectionsService.name);

  constructor(private readonly prisma: PrismaService) {}

  /**
   * Create a new connection between two users at an event.
   * Returns existing connection if one already exists (upsert behavior).
   */
  async createConnection(data: CreateConnectionDto): Promise<Connection> {
    // Normalize user order to prevent duplicate connections (A-B vs B-A)
    const [userAId, userBId] = [data.userAId, data.userBId].sort();

    try {
      const connection = await this.prisma.connection.upsert({
        where: {
          userAId_userBId_eventId: {
            userAId,
            userBId,
            eventId: data.eventId,
          },
        },
        update: {
          // If connection exists, we might update the message if provided
          ...(data.initialMessage && { initialMessage: data.initialMessage }),
        },
        create: {
          userAId,
          userBId,
          eventId: data.eventId,
          connectionType: data.connectionType || ConnectionType.PROXIMITY_PING,
          initialMessage: data.initialMessage,
        },
      });

      this.logger.log(
        `Connection created/updated: ${connection.id} between ${userAId} and ${userBId}`,
      );
      return connection;
    } catch (error) {
      this.logger.error('Failed to create connection', error);
      throw error;
    }
  }

  /**
   * Get all connections for a user at a specific event.
   */
  async getUserEventConnections(
    userId: string,
    eventId: string,
  ): Promise<ConnectionWithContext[]> {
    const connections = await this.prisma.connection.findMany({
      where: {
        eventId,
        OR: [{ userAId: userId }, { userBId: userId }],
      },
      include: {
        userA: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        userB: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        contexts: true,
      },
      orderBy: {
        connectedAt: 'desc',
      },
    });

    return connections;
  }

  /**
   * Get all connections for a user across all events.
   */
  async getUserConnections(userId: string): Promise<ConnectionWithContext[]> {
    const connections = await this.prisma.connection.findMany({
      where: {
        OR: [{ userAId: userId }, { userBId: userId }],
      },
      include: {
        userA: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        userB: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        contexts: true,
      },
      orderBy: {
        connectedAt: 'desc',
      },
    });

    return connections;
  }

  /**
   * Get a single connection with full context.
   */
  async getConnectionWithContext(
    connectionId: string,
  ): Promise<ConnectionWithContext> {
    const connection = await this.prisma.connection.findUnique({
      where: { id: connectionId },
      include: {
        userA: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        userB: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        contexts: true,
      },
    });

    if (!connection) {
      throw new NotFoundException(`Connection ${connectionId} not found`);
    }

    return connection;
  }

  /**
   * Mark follow-up as sent for a connection.
   */
  async markFollowUpSent(connectionId: string): Promise<void> {
    await this.prisma.connection.update({
      where: { id: connectionId },
      data: { followUpSentAt: new Date() },
    });
    this.logger.log(`Follow-up marked as sent for connection ${connectionId}`);
  }

  /**
   * Mark follow-up as opened (email tracking).
   */
  async markFollowUpOpened(connectionId: string): Promise<void> {
    await this.prisma.connection.update({
      where: { id: connectionId },
      data: { followUpOpenedAt: new Date() },
    });
  }

  /**
   * Mark follow-up as replied.
   */
  async markFollowUpReplied(connectionId: string): Promise<void> {
    await this.prisma.connection.update({
      where: { id: connectionId },
      data: { followUpRepliedAt: new Date() },
    });
  }

  /**
   * Report an outcome for a connection.
   */
  async reportOutcome(
    connectionId: string,
    data: ReportOutcomeDto,
  ): Promise<Connection> {
    const connection = await this.prisma.connection.update({
      where: { id: connectionId },
      data: {
        outcomeType: data.outcomeType,
        outcomeNotes: data.outcomeNotes,
        outcomeReportedAt: new Date(),
        meetingScheduled: data.meetingScheduled ?? false,
        meetingDate: data.meetingDate ? new Date(data.meetingDate) : null,
      },
    });

    this.logger.log(
      `Outcome reported for connection ${connectionId}: ${data.outcomeType}`,
    );
    return connection;
  }

  /**
   * Get networking statistics for an event.
   */
  async getEventNetworkingStats(eventId: string): Promise<EventNetworkingStats> {
    const connections = await this.prisma.connection.findMany({
      where: { eventId },
      include: {
        userA: { select: { id: true, firstName: true, lastName: true } },
        userB: { select: { id: true, firstName: true, lastName: true } },
      },
    });

    // Calculate unique networkers
    const uniqueUsers = new Set<string>();
    connections.forEach((c) => {
      uniqueUsers.add(c.userAId);
      uniqueUsers.add(c.userBId);
    });

    // Count follow-ups sent
    const followUpsSent = connections.filter((c) => c.followUpSentAt).length;

    // Count meetings scheduled
    const meetingsScheduled = connections.filter((c) => c.meetingScheduled).length;

    // Count reported outcomes
    const reportedOutcomes = connections.filter((c) => c.outcomeType).length;

    // Group by connection type
    const connectionsByType = connections.reduce(
      (acc, c) => {
        acc[c.connectionType] = (acc[c.connectionType] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>,
    );

    // Find top connectors
    const connectionCountByUser = new Map<
      string,
      { name: string; count: number }
    >();
    connections.forEach((c) => {
      const userAName =
        `${c.userA.firstName || ''} ${c.userA.lastName || ''}`.trim() ||
        'Unknown';
      const userBName =
        `${c.userB.firstName || ''} ${c.userB.lastName || ''}`.trim() ||
        'Unknown';

      const existingA = connectionCountByUser.get(c.userAId) || {
        name: userAName,
        count: 0,
      };
      existingA.count++;
      connectionCountByUser.set(c.userAId, existingA);

      const existingB = connectionCountByUser.get(c.userBId) || {
        name: userBName,
        count: 0,
      };
      existingB.count++;
      connectionCountByUser.set(c.userBId, existingB);
    });

    const topConnectors = Array.from(connectionCountByUser.entries())
      .map(([userId, data]) => ({
        userId,
        name: data.name,
        connectionCount: data.count,
      }))
      .sort((a, b) => b.connectionCount - a.connectionCount)
      .slice(0, 10);

    return {
      totalConnections: connections.length,
      uniqueNetworkers: uniqueUsers.size,
      followUpsSent,
      followUpRate:
        connections.length > 0 ? (followUpsSent / connections.length) * 100 : 0,
      meetingsScheduled,
      reportedOutcomes,
      connectionsByType,
      topConnectors,
    };
  }

  /**
   * Get networking statistics for a user.
   */
  async getUserNetworkingStats(userId: string): Promise<UserNetworkingStats> {
    const connections = await this.prisma.connection.findMany({
      where: {
        OR: [{ userAId: userId }, { userBId: userId }],
      },
    });

    // Count unique events
    const uniqueEvents = new Set(connections.map((c) => c.eventId));

    // Calculate follow-up rate
    const followUpsSent = connections.filter((c) => c.followUpSentAt).length;
    const followUpRate =
      connections.length > 0 ? (followUpsSent / connections.length) * 100 : 0;

    // Calculate outcome rate
    const outcomesReported = connections.filter((c) => c.outcomeType).length;
    const outcomeRate =
      connections.length > 0 ? (outcomesReported / connections.length) * 100 : 0;

    // Group by event
    const connectionsByEventMap = connections.reduce(
      (acc, c) => {
        acc[c.eventId] = (acc[c.eventId] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>,
    );

    const connectionsByEvent = Object.entries(connectionsByEventMap).map(
      ([eventId, count]) => ({ eventId, count }),
    );

    return {
      totalConnections: connections.length,
      eventCount: uniqueEvents.size,
      followUpRate,
      outcomeRate,
      connectionsByEvent,
    };
  }

  /**
   * Get all connections for an event (for organizer analytics).
   */
  async getEventConnections(eventId: string): Promise<ConnectionWithContext[]> {
    return this.prisma.connection.findMany({
      where: { eventId },
      include: {
        userA: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        userB: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        contexts: true,
      },
      orderBy: {
        connectedAt: 'desc',
      },
    });
  }

  /**
   * Check if a connection exists between two users at an event.
   */
  async connectionExists(
    userAId: string,
    userBId: string,
    eventId: string,
  ): Promise<boolean> {
    const [sortedUserAId, sortedUserBId] = [userAId, userBId].sort();

    const connection = await this.prisma.connection.findUnique({
      where: {
        userAId_userBId_eventId: {
          userAId: sortedUserAId,
          userBId: sortedUserBId,
          eventId,
        },
      },
    });

    return !!connection;
  }

  // ============================================
  // Activity Logging & Strength Calculation
  // ============================================

  /**
   * Log an activity for a connection and recalculate strength.
   * @param params - Activity parameters
   * @param callerUserId - Optional: User ID of caller for authorization check
   */
  async logActivity(
    params: LogActivityParams,
    callerUserId?: string,
  ): Promise<void> {
    const { connectionId, activityType, initiatorId, description, metadata } =
      params;

    // Verify connection exists and optionally check authorization
    const connection = await this.prisma.connection.findUnique({
      where: { id: connectionId },
      select: { id: true, userAId: true, userBId: true },
    });

    if (!connection) {
      throw new NotFoundException(`Connection ${connectionId} not found`);
    }

    // Authorization check: if callerUserId provided, verify they're part of the connection
    if (
      callerUserId &&
      connection.userAId !== callerUserId &&
      connection.userBId !== callerUserId
    ) {
      this.logger.warn(
        `Unauthorized logActivity attempt: User ${callerUserId} for connection ${connectionId}`,
      );
      throw new NotFoundException(`Connection ${connectionId} not found`);
    }

    // Create activity record and update connection in a transaction
    await this.prisma.$transaction(async (tx) => {
      // Log the activity
      await tx.connectionActivity.create({
        data: {
          connectionId,
          activityType,
          initiatorId,
          description,
          metadata: metadata ?? Prisma.JsonNull,
        },
      });

      // Update interaction tracking
      await tx.connection.update({
        where: { id: connectionId },
        data: {
          lastInteractionAt: new Date(),
          interactionCount: { increment: 1 },
        },
      });

      // Recalculate strength
      await this.calculateAndUpdateStrength(connectionId, tx);
    });

    this.logger.log(
      `Activity logged for connection ${connectionId}: ${activityType}`,
    );
  }

  /**
   * Calculate connection strength based on activity history and update.
   * Optimized to only fetch recent activities needed for strength determination.
   */
  private async calculateAndUpdateStrength(
    connectionId: string,
    tx?: Prisma.TransactionClient,
  ): Promise<ConnectionStrength> {
    const client = tx ?? this.prisma;

    // Fetch connection with limited recent activities for performance
    // We only need to check if certain activity types exist, not full history
    const connection = await client.connection.findUnique({
      where: { id: connectionId },
      select: {
        id: true,
        strength: true,
        interactionCount: true,
        activities: {
          select: { activityType: true },
          orderBy: { createdAt: 'desc' },
          take: 50, // Limit to recent activities - sufficient for strength calc
        },
      },
    });

    if (!connection) {
      throw new NotFoundException(`Connection ${connectionId} not found`);
    }

    const activityTypes = connection.activities.map((a) => a.activityType);
    const interactionCount = connection.interactionCount;

    // Determine strength level
    let newStrength: ConnectionStrength = ConnectionStrength.WEAK;

    // Check for STRONG indicators first (highest priority)
    const hasStrongActivity = activityTypes.some((type) =>
      STRENGTH_THRESHOLDS.STRONG_ACTIVITY_TYPES.includes(type),
    );

    if (
      hasStrongActivity ||
      interactionCount >= STRENGTH_THRESHOLDS.STRONG_MIN_INTERACTIONS
    ) {
      newStrength = ConnectionStrength.STRONG;
    }
    // Check for MODERATE indicators
    else {
      const hasModerateActivity = activityTypes.some((type) =>
        STRENGTH_THRESHOLDS.MODERATE_ACTIVITY_TYPES.includes(type),
      );

      if (
        hasModerateActivity ||
        interactionCount >= STRENGTH_THRESHOLDS.MODERATE_MIN_INTERACTIONS
      ) {
        newStrength = ConnectionStrength.MODERATE;
      }
    }

    // Update if changed
    if (connection.strength !== newStrength) {
      await client.connection.update({
        where: { id: connectionId },
        data: { strength: newStrength },
      });

      this.logger.log(
        `Connection ${connectionId} strength updated: ${connection.strength} -> ${newStrength}`,
      );
    }

    return newStrength;
  }

  /**
   * Get connection with full activity history.
   */
  async getConnectionWithActivities(
    connectionId: string,
  ): Promise<ConnectionWithContext> {
    const connection = await this.prisma.connection.findUnique({
      where: { id: connectionId },
      include: {
        userA: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        userB: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        contexts: true,
        activities: {
          orderBy: { createdAt: 'desc' },
        },
      },
    });

    if (!connection) {
      throw new NotFoundException(`Connection ${connectionId} not found`);
    }

    return connection;
  }

  /**
   * Get all connections for a user with activities, filtered by strength.
   */
  async getUserConnectionsByStrength(
    userId: string,
    strength?: ConnectionStrength,
  ): Promise<ConnectionWithContext[]> {
    const whereClause: Prisma.ConnectionWhereInput = {
      OR: [{ userAId: userId }, { userBId: userId }],
    };

    if (strength) {
      whereClause.strength = strength;
    }

    return this.prisma.connection.findMany({
      where: whereClause,
      include: {
        userA: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        userB: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        contexts: true,
        activities: {
          orderBy: { createdAt: 'desc' },
          take: 10, // Limit activities for performance
        },
      },
      orderBy: [{ strength: 'desc' }, { lastInteractionAt: 'desc' }],
    });
  }

  /**
   * Get connections pending follow-up (connected but no follow-up sent).
   */
  async getConnectionsPendingFollowUp(
    userId: string,
    eventId?: string,
  ): Promise<ConnectionWithContext[]> {
    const whereClause: Prisma.ConnectionWhereInput = {
      OR: [{ userAId: userId }, { userBId: userId }],
      followUpSentAt: null,
    };

    if (eventId) {
      whereClause.eventId = eventId;
    }

    return this.prisma.connection.findMany({
      where: whereClause,
      include: {
        userA: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        userB: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        contexts: true,
      },
      orderBy: { connectedAt: 'desc' },
    });
  }

  /**
   * Get connections that need nurturing (no activity in specified days).
   */
  async getStaleConnections(
    userId: string,
    staleDays = 30,
  ): Promise<ConnectionWithContext[]> {
    const staleDate = new Date();
    staleDate.setDate(staleDate.getDate() - staleDays);

    return this.prisma.connection.findMany({
      where: {
        OR: [{ userAId: userId }, { userBId: userId }],
        lastInteractionAt: {
          lt: staleDate,
        },
        strength: {
          not: ConnectionStrength.WEAK, // Only nurture moderate/strong connections
        },
      },
      include: {
        userA: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        userB: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            email: true,
            avatarUrl: true,
          },
        },
        contexts: true,
        activities: {
          orderBy: { createdAt: 'desc' },
          take: 5,
        },
      },
      orderBy: { lastInteractionAt: 'asc' },
    });
  }

  /**
   * Batch update connection activities (e.g., from huddle completion).
   */
  async logBulkActivity(
    connectionIds: string[],
    activityType: ConnectionActivityType,
    metadata?: Record<string, unknown>,
  ): Promise<void> {
    if (connectionIds.length === 0) return;

    await this.prisma.$transaction(async (tx) => {
      // Create all activities
      await tx.connectionActivity.createMany({
        data: connectionIds.map((connectionId) => ({
          connectionId,
          activityType,
          metadata: metadata ?? Prisma.JsonNull,
        })),
      });

      // Update all connections
      await tx.connection.updateMany({
        where: { id: { in: connectionIds } },
        data: {
          lastInteractionAt: new Date(),
          interactionCount: { increment: 1 },
        },
      });

      // Recalculate strength for each (could be optimized with batch logic)
      for (const connectionId of connectionIds) {
        await this.calculateAndUpdateStrength(connectionId, tx);
      }
    });

    this.logger.log(
      `Bulk activity logged for ${connectionIds.length} connections: ${activityType}`,
    );
  }

  /**
   * Store AI-generated follow-up message suggestion.
   */
  async storeFollowUpSuggestion(
    connectionId: string,
    message: string,
  ): Promise<void> {
    await this.prisma.connection.update({
      where: { id: connectionId },
      data: { followUpMessage: message },
    });
  }

  /**
   * Get connection strength distribution for user analytics.
   */
  async getUserStrengthDistribution(
    userId: string,
  ): Promise<Record<ConnectionStrength, number>> {
    const connections = await this.prisma.connection.findMany({
      where: {
        OR: [{ userAId: userId }, { userBId: userId }],
      },
      select: { strength: true },
    });

    const distribution: Record<ConnectionStrength, number> = {
      [ConnectionStrength.WEAK]: 0,
      [ConnectionStrength.MODERATE]: 0,
      [ConnectionStrength.STRONG]: 0,
    };

    connections.forEach((c) => {
      distribution[c.strength]++;
    });

    return distribution;
  }
}
