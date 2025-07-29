export interface DashboardData {
  totalMessages: number;
  totalVotes: number;
  totalQuestions: number;
  totalUpvotes: number;
  totalReactions: number;
  liveCheckInFeed: CheckInFeedItem[];
}
import { Inject, Injectable, Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { DashboardGateway } from './dashboard.gateway';
import { CapacityUpdateDto } from './dto/capacity-update.dto';

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

// Define the shape of the incoming payload
interface MultitenantMetricsDto {
  orgId: string;
  metrics: {
    activeConnections: number;
    messagesPerSecond: number;
    averageLatency: number;
  };
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
    private readonly dashboardGateway: DashboardGateway,
  ) {}

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
  @OnEvent('analytics-events')
  @OnEvent('platform.analytics.check-in.v1')
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
   *
   * @param eventId - The event ID.
   * @param checkInData - Check-in data to add to the feed.
   * @returns Promise<void>
   */
  private async updateCheckInFeed(
    eventId: string,
    checkInData: CheckInFeedItem,
  ): Promise<void> {
    const redisKey = `dashboard:feed:check-in:${eventId}`;
    await this.redis.lpush(redisKey, JSON.stringify(checkInData));
    await this.redis.ltrim(redisKey, 0, 9);
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
   * Listens for capacity update events and triggers a broadcast.
   */
  @OnEvent('capacity-events')
  handleCapacityUpdate(payload: CapacityUpdateDto) {
    this.logger.log(
      `Processing capacity update for resource: ${payload.resourceId}`,
    );
    this.dashboardGateway.broadcastCapacityUpdate(payload);
  }

  /**
   * Listens for system-wide metric events, finds all active events for the org,
   * and triggers a broadcast to all relevant dashboards.
   */
  @OnEvent('system-metrics-events')
  async handleSystemMetrics(payload: MultitenantMetricsDto) {
    this.logger.log(`Processing system metrics for org: ${payload.orgId}`);

    // 1. Get the list of all active event IDs for this organization from Redis.
    const activeEventIds = await this.redis.smembers(
      `org:active_events:${payload.orgId}`,
    );

    if (activeEventIds.length === 0) {
      this.logger.log(
        `No active event dashboards for org ${payload.orgId}. Skipping broadcast.`,
      );
      return;
    }

    this.dashboardGateway.broadcastSystemMetrics(activeEventIds, payload);
  }
}
