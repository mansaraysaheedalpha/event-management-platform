//src/networking/analytics/analytics.service.ts
import { Injectable, Logger, Inject } from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { Redis } from 'ioredis';
import { OutcomeType } from '@prisma/client';

// Cache TTL in seconds
const ANALYTICS_CACHE_TTL = 60; // 1 minute for real-time feel
const GRAPH_CACHE_TTL = 300; // 5 minutes for graph data

export interface OutcomeBreakdown {
  type: string;
  count: number;
  percentage: number;
}

export interface ConnectionTypeBreakdown {
  type: string;
  count: number;
  percentage: number;
}

export interface TopConnector {
  userId: string;
  name: string;
  email: string;
  connectionCount: number;
  followUpRate: number;
}

export interface NetworkNode {
  id: string;
  name: string;
  email: string;
  connectionCount: number;
}

export interface NetworkEdge {
  source: string;
  target: string;
  connectionId: string;
  hasOutcome: boolean;
}

export interface ConnectionNetworkGraph {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
}

export interface TimeSeriesDataPoint {
  date: string;
  connections: number;
  followUps: number;
  outcomes: number;
}

export interface EventAnalytics {
  totalConnections: number;
  uniqueNetworkers: number;
  averageConnectionsPerAttendee: number;
  followUpsSent: number;
  followUpsOpened: number;
  followUpsReplied: number;
  followUpSentRate: number;
  followUpOpenRate: number;
  followUpReplyRate: number;
  meetingsScheduled: number;
  reportedOutcomes: number;
  outcomeRate: number;
  outcomeBreakdown: OutcomeBreakdown[];
  connectionsByType: ConnectionTypeBreakdown[];
  topConnectors: TopConnector[];
  dailyActivity: TimeSeriesDataPoint[];
  networkingScore: number;
}

export interface UserAnalytics {
  totalConnections: number;
  totalEvents: number;
  followUpsSent: number;
  followUpRate: number;
  outcomesReported: number;
  outcomeRate: number;
  outcomeBreakdown: OutcomeBreakdown[];
  connectionsByEvent: Array<{
    eventId: string;
    eventName: string;
    connectionCount: number;
    date: string;
  }>;
  recentConnections: Array<{
    id: string;
    otherUserName: string;
    otherUserEmail: string;
    eventName: string;
    connectedAt: string;
    hasFollowUp: boolean;
    hasOutcome: boolean;
  }>;
}

@Injectable()
export class NetworkingAnalyticsService {
  private readonly logger = new Logger(NetworkingAnalyticsService.name);

  constructor(
    private readonly prisma: PrismaService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
  ) {}

  async getEventAnalytics(eventId: string): Promise<EventAnalytics> {
    // Check cache first
    const cacheKey = `analytics:event:${eventId}`;
    const cached = await this.redis.get(cacheKey);
    if (cached) {
      this.logger.debug(`Cache hit for event analytics: ${eventId}`);
      return JSON.parse(cached);
    }

    const connections = await this.prisma.connection.findMany({
      where: { eventId },
      include: {
        userA: { select: { id: true, firstName: true, lastName: true, email: true } },
        userB: { select: { id: true, firstName: true, lastName: true, email: true } },
      },
      orderBy: { connectedAt: 'asc' },
    });

    const uniqueUsers = new Set<string>();
    connections.forEach((c) => {
      uniqueUsers.add(c.userAId);
      uniqueUsers.add(c.userBId);
    });

    // Estimate attendee count from unique networkers
    // In production, this would call the event-lifecycle-service API
    const attendeeCount = uniqueUsers.size > 0 ? uniqueUsers.size * 2 : 0;

    const followUpsSent = connections.filter((c) => c.followUpSentAt).length;
    const followUpsOpened = connections.filter((c) => c.followUpOpenedAt).length;
    const followUpsReplied = connections.filter((c) => c.followUpRepliedAt).length;
    const meetingsScheduled = connections.filter((c) => c.meetingScheduled).length;
    const withOutcomes = connections.filter((c) => c.outcomeType);
    const reportedOutcomes = withOutcomes.length;

    const outcomeBreakdown = this.calculateOutcomeBreakdown(withOutcomes);
    const connectionsByType = this.calculateConnectionTypeBreakdown(connections);
    const topConnectors = this.calculateTopConnectors(connections);
    const dailyActivity = this.calculateDailyActivity(connections);
    const networkingScore = this.calculateNetworkingScore(
      connections.length,
      uniqueUsers.size,
      followUpsSent,
      reportedOutcomes,
    );
    const totalConnections = connections.length;

    const result: EventAnalytics = {
      totalConnections,
      uniqueNetworkers: uniqueUsers.size,
      averageConnectionsPerAttendee: attendeeCount > 0 ? totalConnections / attendeeCount : 0,
      followUpsSent,
      followUpsOpened,
      followUpsReplied,
      followUpSentRate: totalConnections > 0 ? (followUpsSent / totalConnections) * 100 : 0,
      followUpOpenRate: followUpsSent > 0 ? (followUpsOpened / followUpsSent) * 100 : 0,
      followUpReplyRate: followUpsSent > 0 ? (followUpsReplied / followUpsSent) * 100 : 0,
      meetingsScheduled,
      reportedOutcomes,
      outcomeRate: totalConnections > 0 ? (reportedOutcomes / totalConnections) * 100 : 0,
      outcomeBreakdown,
      connectionsByType,
      topConnectors,
      dailyActivity,
      networkingScore,
    };

    // Cache the result
    await this.redis.setex(cacheKey, ANALYTICS_CACHE_TTL, JSON.stringify(result));
    this.logger.debug(`Cached event analytics: ${eventId}`);

    return result;
  }

  async getConnectionGraph(eventId: string): Promise<ConnectionNetworkGraph> {
    // Check cache first
    const cacheKey = `analytics:graph:${eventId}`;
    const cached = await this.redis.get(cacheKey);
    if (cached) {
      this.logger.debug(`Cache hit for connection graph: ${eventId}`);
      return JSON.parse(cached);
    }

    const connections = await this.prisma.connection.findMany({
      where: { eventId },
      include: {
        userA: { select: { id: true, firstName: true, lastName: true, email: true } },
        userB: { select: { id: true, firstName: true, lastName: true, email: true } },
      },
    });

    const nodesMap = new Map<string, NetworkNode>();

    connections.forEach((conn) => {
      if (!nodesMap.has(conn.userAId)) {
        nodesMap.set(conn.userAId, {
          id: conn.userAId,
          name: [conn.userA.firstName, conn.userA.lastName].filter(Boolean).join(' ') || 'Unknown',
          email: conn.userA.email,
          connectionCount: 0,
        });
      }
      nodesMap.get(conn.userAId)!.connectionCount++;

      if (!nodesMap.has(conn.userBId)) {
        nodesMap.set(conn.userBId, {
          id: conn.userBId,
          name: [conn.userB.firstName, conn.userB.lastName].filter(Boolean).join(' ') || 'Unknown',
          email: conn.userB.email,
          connectionCount: 0,
        });
      }
      nodesMap.get(conn.userBId)!.connectionCount++;
    });

    const edges: NetworkEdge[] = connections.map((conn) => ({
      source: conn.userAId,
      target: conn.userBId,
      connectionId: conn.id,
      hasOutcome: !!conn.outcomeType,
    }));

    const result: ConnectionNetworkGraph = { nodes: Array.from(nodesMap.values()), edges };

    // Cache the result
    await this.redis.setex(cacheKey, GRAPH_CACHE_TTL, JSON.stringify(result));
    this.logger.debug(`Cached connection graph: ${eventId}`);

    return result;
  }

  async getUserAnalytics(userId: string): Promise<UserAnalytics> {
    const connections = await this.prisma.connection.findMany({
      where: { OR: [{ userAId: userId }, { userBId: userId }] },
      include: {
        userA: { select: { id: true, firstName: true, lastName: true, email: true } },
        userB: { select: { id: true, firstName: true, lastName: true, email: true } },
      },
      orderBy: { connectedAt: 'desc' },
    });

    const eventIds = [...new Set(connections.map((c) => c.eventId))];
    const followUpsSent = connections.filter((c) => c.followUpSentAt).length;
    const withOutcomes = connections.filter((c) => c.outcomeType);
    const outcomeBreakdown = this.calculateOutcomeBreakdown(withOutcomes);

    const connectionsByEventMap = new Map<string, number>();
    connections.forEach((c) => {
      connectionsByEventMap.set(c.eventId, (connectionsByEventMap.get(c.eventId) || 0) + 1);
    });

    const connectionsByEvent = Array.from(connectionsByEventMap.entries()).map(
      ([eventId, count]) => ({
        eventId,
        eventName: 'Event ' + eventId.slice(0, 8),
        connectionCount: count,
        date: connections.find((c) => c.eventId === eventId)?.connectedAt.toISOString() || '',
      }),
    );

    const recentConnections = connections.slice(0, 10).map((conn) => {
      const isUserA = conn.userAId === userId;
      const otherUser = isUserA ? conn.userB : conn.userA;
      return {
        id: conn.id,
        otherUserName: [otherUser.firstName, otherUser.lastName].filter(Boolean).join(' ') || 'Unknown',
        otherUserEmail: otherUser.email,
        eventName: 'Event ' + conn.eventId.slice(0, 8),
        connectedAt: conn.connectedAt.toISOString(),
        hasFollowUp: !!conn.followUpSentAt,
        hasOutcome: !!conn.outcomeType,
      };
    });

    return {
      totalConnections: connections.length,
      totalEvents: eventIds.length,
      followUpsSent,
      followUpRate: connections.length > 0 ? (followUpsSent / connections.length) * 100 : 0,
      outcomesReported: withOutcomes.length,
      outcomeRate: connections.length > 0 ? (withOutcomes.length / connections.length) * 100 : 0,
      outcomeBreakdown,
      connectionsByEvent,
      recentConnections,
    };
  }

  async getOutcomeBreakdown(eventId: string): Promise<OutcomeBreakdown[]> {
    const connections = await this.prisma.connection.findMany({
      where: { eventId, outcomeType: { not: null } },
    });
    return this.calculateOutcomeBreakdown(connections);
  }

  private calculateOutcomeBreakdown(
    connections: Array<{ outcomeType: OutcomeType | null }>,
  ): OutcomeBreakdown[] {
    const total = connections.length;
    if (total === 0) return [];

    const countByType = new Map<string, number>();
    connections.forEach((c) => {
      if (c.outcomeType) {
        countByType.set(c.outcomeType, (countByType.get(c.outcomeType) || 0) + 1);
      }
    });

    return Array.from(countByType.entries())
      .map(([type, count]) => ({ type, count, percentage: (count / total) * 100 }))
      .sort((a, b) => b.count - a.count);
  }

  private calculateConnectionTypeBreakdown(
    connections: Array<{ connectionType: string }>,
  ): ConnectionTypeBreakdown[] {
    const total = connections.length;
    if (total === 0) return [];

    const countByType = new Map<string, number>();
    connections.forEach((c) => {
      countByType.set(c.connectionType, (countByType.get(c.connectionType) || 0) + 1);
    });

    return Array.from(countByType.entries())
      .map(([type, count]) => ({ type, count, percentage: (count / total) * 100 }))
      .sort((a, b) => b.count - a.count);
  }

  private calculateTopConnectors(
    connections: Array<{
      userAId: string;
      userBId: string;
      followUpSentAt: Date | null;
      userA: { firstName: string | null; lastName: string | null; email: string };
      userB: { firstName: string | null; lastName: string | null; email: string };
    }>,
  ): TopConnector[] {
    const userStats = new Map<
      string,
      { name: string; email: string; connections: number; followUps: number }
    >();

    connections.forEach((conn) => {
      if (!userStats.has(conn.userAId)) {
        userStats.set(conn.userAId, {
          name: [conn.userA.firstName, conn.userA.lastName].filter(Boolean).join(' ') || 'Unknown',
          email: conn.userA.email,
          connections: 0,
          followUps: 0,
        });
      }
      const statsA = userStats.get(conn.userAId)!;
      statsA.connections++;
      if (conn.followUpSentAt) statsA.followUps++;

      if (!userStats.has(conn.userBId)) {
        userStats.set(conn.userBId, {
          name: [conn.userB.firstName, conn.userB.lastName].filter(Boolean).join(' ') || 'Unknown',
          email: conn.userB.email,
          connections: 0,
          followUps: 0,
        });
      }
      const statsB = userStats.get(conn.userBId)!;
      statsB.connections++;
      if (conn.followUpSentAt) statsB.followUps++;
    });

    return Array.from(userStats.entries())
      .map(([userId, stats]) => ({
        userId,
        name: stats.name,
        email: stats.email,
        connectionCount: stats.connections,
        followUpRate: stats.connections > 0 ? (stats.followUps / stats.connections) * 100 : 0,
      }))
      .sort((a, b) => b.connectionCount - a.connectionCount)
      .slice(0, 10);
  }

  private calculateDailyActivity(
    connections: Array<{
      connectedAt: Date;
      followUpSentAt: Date | null;
      outcomeType: OutcomeType | null;
    }>,
  ): TimeSeriesDataPoint[] {
    if (connections.length === 0) return [];

    const dailyMap = new Map<
      string,
      { connections: number; followUps: number; outcomes: number }
    >();

    connections.forEach((conn) => {
      const date = conn.connectedAt.toISOString().split('T')[0];
      if (!dailyMap.has(date)) {
        dailyMap.set(date, { connections: 0, followUps: 0, outcomes: 0 });
      }
      const day = dailyMap.get(date)!;
      day.connections++;
      if (conn.followUpSentAt) day.followUps++;
      if (conn.outcomeType) day.outcomes++;
    });

    return Array.from(dailyMap.entries())
      .map(([date, stats]) => ({ date, ...stats }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }

  private calculateNetworkingScore(
    totalConnections: number,
    uniqueNetworkers: number,
    followUpsSent: number,
    reportedOutcomes: number,
  ): number {
    const connectionScore = Math.min(totalConnections / 100, 1) * 100;
    const followUpRate = totalConnections > 0 ? followUpsSent / totalConnections : 0;
    const followUpScore = Math.min(followUpRate / 0.5, 1) * 100;
    const outcomeRate = totalConnections > 0 ? reportedOutcomes / totalConnections : 0;
    const outcomeScore = Math.min(outcomeRate / 0.2, 1) * 100;
    return Math.round(connectionScore * 0.3 + followUpScore * 0.4 + outcomeScore * 0.3);
  }
}
