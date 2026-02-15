//src/live/dashboard/dashboard.service.ts
export interface DashboardData {
  totalMessages: number;
  totalVotes: number;
  totalQuestions: number;
  totalUpvotes: number;
  totalReactions: number;
  liveCheckInFeed: CheckInFeedItem[];
}

export interface EngagementBreakdownData {
  qaParticipation: number;
  qaParticipationCount: number;
  qaTotal: number;
  pollResponseRate: number;
  pollResponseCount: number;
  pollTotal: number;
  chatActivityRate: number;
  chatMessageCount: number;
  chatParticipants: number;
  chatTotal: number;
}

import { Inject, Injectable, Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { PrismaService } from 'src/prisma.service';

// Supporting types and type guard (unchanged)
type AnalyticsEventType =
  | 'MESSAGE_SENT'
  | 'POLL_VOTE_CAST'
  | 'QUESTION_ASKED'
  | 'QUESTION_UPVOTED'
  | 'REACTION_SENT'
  | 'CHECK_IN_PROCESSED';

interface AnalyticsEventPayload {
  type: AnalyticsEventType;
  eventId: string;
  organizationId: string;
  sessionId?: string;
  checkInData?: CheckInFeedItem;
}

interface CheckInFeedItem {
  id: string;
  name: string;
}

function isAnalyticsEventPayload(
  payload: unknown,
): payload is AnalyticsEventPayload {
  const p = payload as AnalyticsEventPayload;
  return (
    typeof p === 'object' &&
    p !== null &&
    typeof p.type === 'string' &&
    typeof p.eventId === 'string'
  );
}

/**
 * Service that processes real-time analytics events
 * and provides aggregated dashboard data.
 *
 * Usage:
 *  - Listens to analytics events like 'MESSAGE_SENT', 'CHECK_IN_PROCESSED'.
 *  - Aggregates counts in Redis hashes.
 *  - Maintains a live check-in feed capped at 10 items.
 *  - Provides a method to fetch dashboard data for broadcasting.
 */
@Injectable()
export class DashboardService {
  private readonly logger = new Logger(DashboardService.name);

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly prisma: PrismaService,
  ) {}

  /**
   * Listens to analytics events from Redis Pub/Sub and updates dashboard metrics.
   * This wires up the 'analytics-events' channel to the handleAnalyticsEvent method.
   */
  @OnEvent('analytics-events')
  async onAnalyticsEvent(payload: unknown): Promise<void> {
    await this.handleAnalyticsEvent(payload);
  }

  /**
   * Listens to analytics events and updates Redis stats accordingly.
   *
   * @param payload - The analytics event payload. Should match the AnalyticsEventPayload type:
   *   {
   *     type: 'MESSAGE_SENT' | 'POLL_VOTE_CAST' | 'QUESTION_ASKED' | 'QUESTION_UPVOTED' | 'REACTION_SENT' | 'CHECK_IN_PROCESSED',
   *     eventId: string,
   *     organizationId: string,
   *     sessionId?: string,
   *     checkInData?: { id: string, name: string }
   *   }
   * If the payload is malformed, the event is ignored and a warning is logged.
   * For valid events, increments counters in Redis and updates the live check-in feed for 'CHECK_IN_PROCESSED'.
   *
   * @returns Promise<void> Resolves when event handling and Redis updates are complete.
   */
  async handleAnalyticsEvent(payload: unknown): Promise<void> {
    if (!isAnalyticsEventPayload(payload)) {
      this.logger.warn('Received malformed analytics payload', payload);
      return;
    }
    this.logger.log(`Processing analytics event: ${payload.type}`);
    const eventKey = `dashboard:analytics:${payload.eventId}`;

    switch (payload.type) {
      case 'MESSAGE_SENT':
        await this.redis.hincrby(eventKey, 'totalMessages', 1);
        break;
      case 'POLL_VOTE_CAST':
        await this.redis.hincrby(eventKey, 'totalVotes', 1);
        break;
      case 'QUESTION_ASKED':
        await this.redis.hincrby(eventKey, 'totalQuestions', 1);
        break;
      case 'QUESTION_UPVOTED':
        await this.redis.hincrby(eventKey, 'totalUpvotes', 1);
        break;
      case 'REACTION_SENT':
        await this.redis.hincrby(eventKey, 'totalReactions', 1);
        break;
      case 'CHECK_IN_PROCESSED':
        if (payload.checkInData) {
          await this.updateCheckInFeed(payload.eventId, payload.checkInData);
        } else {
          this.logger.warn(
            `CHECK_IN_PROCESSED event missing checkInData for eventId: ${payload.eventId}`,
            payload,
          );
        }
        break;
    }
  }

  /**
   * Updates the live check-in feed in Redis.
   * Anonymizes attendee names to protect PII before broadcasting.
   *
   * @param eventId - The event ID.
   * @param checkInData - Check-in data to add to the feed.
   * @returns Promise<void>
   */
  private async updateCheckInFeed(
    eventId: string,
    checkInData: CheckInFeedItem,
  ): Promise<void> {
    const anonymized = {
      id: checkInData.id, // Keep ID for dedup
      name: this.anonymizeName(checkInData.name), // Show initials only
      timestamp: new Date().toISOString(),
    };
    const redisKey = `dashboard:feed:check-in:${eventId}`;
    await this.redis.lpush(redisKey, JSON.stringify(anonymized));
    await this.redis.ltrim(redisKey, 0, 9);
  }

  /**
   * Anonymizes a full name to initials to protect PII.
   * "John Doe" -> "J. D.", "Alice" -> "A***"
   *
   * @param fullName - The full name to anonymize.
   * @returns Anonymized name string.
   */
  private anonymizeName(fullName: string): string {
    if (!fullName) return 'Attendee';
    const parts = fullName.trim().split(/\s+/);
    if (parts.length === 1) {
      return parts[0].charAt(0).toUpperCase() + '***';
    }
    return (
      parts[0].charAt(0).toUpperCase() +
      '. ' +
      parts[parts.length - 1].charAt(0).toUpperCase() +
      '.'
    );
  }

  /**
   * Fetches aggregated dashboard data and recent check-ins for an event.
   *
   * @param eventId - The event ID.
   * @returns Promise<object> containing counts and live check-in feed.
   */
  async getDashboardData(eventId: string): Promise<DashboardData> {
    const eventKey = `dashboard:analytics:${eventId}`;
    const feedKey = `dashboard:feed:check-in:${eventId}`;

    const results = await this.redis
      .multi()
      .hgetall(eventKey)
      .lrange(feedKey, 0, 9)
      .exec();

    if (!results) {
      this.logger.error(
        `Redis transaction failed for getDashboardData on event ${eventId}`,
      );
      return {
        totalMessages: 0,
        totalVotes: 0,
        totalQuestions: 0,
        totalUpvotes: 0,
        totalReactions: 0,
        liveCheckInFeed: [],
      };
    }

    const [analyticsDataResult, feedDataResult] = results;

    if (analyticsDataResult[0]) throw analyticsDataResult[0];
    if (feedDataResult[0]) throw feedDataResult[0];

    const analytics = analyticsDataResult[1] as Record<string, string>;
    const feedJson = feedDataResult[1] as string[];

    const feed: CheckInFeedItem[] = feedJson.map(
      (item) => JSON.parse(item) as CheckInFeedItem,
    );

    return {
      totalMessages: parseInt(analytics.totalMessages || '0', 10),
      totalVotes: parseInt(analytics.totalVotes || '0', 10),
      totalQuestions: parseInt(analytics.totalQuestions || '0', 10),
      totalUpvotes: parseInt(analytics.totalUpvotes || '0', 10),
      totalReactions: parseInt(analytics.totalReactions || '0', 10),
      liveCheckInFeed: feed,
    };
  }

  /**
   * Retrieves all active event IDs for a given organization.
   *
   * @param orgId - The ID of the organization.
   * @returns A promise that resolves to an array of active event ID strings.
   */
  async getActiveEventIdsForOrg(orgId: string): Promise<string[]> {
    return this.redis.smembers(`org:active_events:${orgId}`);
  }

  /**
   * Gets engagement breakdown data for an event or organization.
   * Queries the database for Q&A, poll, and chat participation metrics.
   *
   * @param eventId - Optional event ID to scope the metrics
   * @param orgId - Organization ID (required if no eventId)
   * @param totalAttendees - Total number of attendees for rate calculations
   * @returns Promise<EngagementBreakdownData> containing participation rates and counts
   */
  async getEngagementBreakdown(
    eventId?: string,
    orgId?: string,
    totalAttendees: number = 0,
  ): Promise<EngagementBreakdownData> {
    try {
      // Build the session filter based on eventId or orgId
      const sessionFilter = eventId
        ? { eventId }
        : orgId
          ? { organizationId: orgId }
          : {};

      // Get all relevant session IDs
      const sessions = await this.prisma.chatSession.findMany({
        where: sessionFilter,
        select: { id: true },
      });
      const sessionIds = sessions.map((s) => s.id);

      if (sessionIds.length === 0) {
        return this.getEmptyEngagementBreakdown(totalAttendees);
      }

      // Query chat metrics
      const [chatMessageCount, chatParticipantsResult] = await Promise.all([
        this.prisma.message.count({
          where: { sessionId: { in: sessionIds } },
        }),
        this.prisma.message.groupBy({
          by: ['authorId'],
          where: { sessionId: { in: sessionIds } },
        }),
      ]);
      const chatParticipants = chatParticipantsResult.length;

      // Query Q&A metrics
      const [qaQuestionCount, qaParticipantsResult] = await Promise.all([
        this.prisma.question.count({
          where: { sessionId: { in: sessionIds } },
        }),
        this.prisma.question.groupBy({
          by: ['authorId'],
          where: { sessionId: { in: sessionIds } },
        }),
      ]);
      const qaParticipationCount = qaParticipantsResult.length;

      // Query Poll metrics
      const [pollVoteCount, pollVotersResult] = await Promise.all([
        this.prisma.pollVote.count({
          where: {
            poll: { sessionId: { in: sessionIds } },
          },
        }),
        this.prisma.pollVote.groupBy({
          by: ['userId'],
          where: {
            poll: { sessionId: { in: sessionIds } },
          },
        }),
      ]);
      const pollResponseCount = pollVotersResult.length;

      // Calculate rates (avoid division by zero)
      const total = totalAttendees > 0 ? totalAttendees : 1;

      return {
        qaParticipation:
          totalAttendees > 0
            ? Math.round((qaParticipationCount / total) * 100 * 10) / 10
            : 0,
        qaParticipationCount,
        qaTotal: totalAttendees,
        pollResponseRate:
          totalAttendees > 0
            ? Math.round((pollResponseCount / total) * 100 * 10) / 10
            : 0,
        pollResponseCount,
        pollTotal: totalAttendees,
        chatActivityRate:
          totalAttendees > 0
            ? Math.round((chatParticipants / total) * 100 * 10) / 10
            : 0,
        chatMessageCount,
        chatParticipants,
        chatTotal: totalAttendees,
      };
    } catch (error) {
      this.logger.error('Failed to get engagement breakdown', error);
      return this.getEmptyEngagementBreakdown(totalAttendees);
    }
  }

  /**
   * Returns an empty engagement breakdown with the given total.
   */
  private getEmptyEngagementBreakdown(
    totalAttendees: number,
  ): EngagementBreakdownData {
    return {
      qaParticipation: 0,
      qaParticipationCount: 0,
      qaTotal: totalAttendees,
      pollResponseRate: 0,
      pollResponseCount: 0,
      pollTotal: totalAttendees,
      chatActivityRate: 0,
      chatMessageCount: 0,
      chatParticipants: 0,
      chatTotal: totalAttendees,
    };
  }
}
