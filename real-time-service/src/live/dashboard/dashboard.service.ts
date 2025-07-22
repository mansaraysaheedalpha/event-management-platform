import { Inject, Injectable, Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/shared.module';

// The complete list of events we want to track for the dashboard
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
  checkInData?: any;
}

// A DTO for the shape of a check-in object
interface CheckInFeedItem {
  id: string;
  name: string;
}

// We define a type guard here, specific to the payloads this service cares about.
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

@Injectable()
export class DashboardService {
  private readonly logger = new Logger(DashboardService.name);

  constructor(@Inject(REDIS_CLIENT) private readonly redis: Redis) {}

  @OnEvent('analytics-events')
  @OnEvent('platform.analytics.check-in.v1')
  async handleAnalyticsEvent(payload: unknown) {
    if (!isAnalyticsEventPayload(payload)) {
      this.logger.warn('Received malformed analytics payload', payload);
      return;
    }
    this.logger.log(`Processing analytics event: ${payload.type}`);
    const eventKey = `dashboard:analytics:${payload.eventId}`;

    // This switch statement is now complete for all our features
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
      // NEW CASE for check-ins
      case 'CHECK_IN_PROCESSED':
        await this.updateCheckInFeed(payload.eventId, payload.checkInData);
        break;
    }
  }

  // NEW private helper to manage the live feed in Redis
  private async updateCheckInFeed(eventId: string, checkInData: any) {
    const redisKey = `dashboard:feed:check-in:${eventId}`;
    // LPUSH adds the new check-in to the start of the list
    await this.redis.lpush(redisKey, JSON.stringify(checkInData));
    // LTRIM keeps the list trimmed to a maximum of 10 recent entries
    await this.redis.ltrim(redisKey, 0, 9);
  }

  async getDashboardData(eventId: string) {
    const eventKey = `dashboard:analytics:${eventId}`;
    const feedKey = `dashboard:feed:check-in:${eventId}`;

    // Use a Redis transaction to fetch all data at once
    // A transaction returns an array of [error, result] tuples, or null on failure.
    const results = await this.redis
      .multi()
      .hgetall(eventKey)
      .lrange(feedKey, 0, 9)
      .exec();

    // 1. Add a null check for the entire transaction
    if (!results) {
      this.logger.error(
        `Redis transaction failed for getDashboardData on event ${eventId}`,
      );
      // Return a default empty state
      return {
        totalMessages: 0,
        totalVotes: 0,
        totalQuestions: 0,
        totalUpvotes: 0,
        totalReactions: 0,
        liveCheckInFeed: [],
      };
    }

    // 2. Safely destructure and check for errors within each command
    const [analyticsDataResult, feedDataResult] = results;

    if (analyticsDataResult[0]) throw analyticsDataResult[0];
    if (feedDataResult[0]) throw feedDataResult[0];

    const analytics = analyticsDataResult[1] as Record<string, string>;
    const feedJson = feedDataResult[1] as string[];

    // 4. Safely parse the feed data with a strong type
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
}
