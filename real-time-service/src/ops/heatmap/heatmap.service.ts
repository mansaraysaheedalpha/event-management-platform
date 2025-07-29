import { Inject, Injectable, Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { Redis } from 'ioredis';
import { PrismaService } from 'src/prisma.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { SessionMetadata } from 'src/common/interfaces/session.interface';

// Type guard to validate the shape of data from the Redis cache
function isSessionMetadata(payload: unknown): payload is SessionMetadata {
  const p = payload as SessionMetadata;
  return (
    typeof p === 'object' &&
    p !== null &&
    typeof p.eventId === 'string' &&
    typeof p.organizationId === 'string'
  );
}

// Define the types of events that contribute to the heatmap
type HeatmapEventType =
  | 'MESSAGE_SENT'
  | 'QUESTION_ASKED'
  | 'QUESTION_UPVOTED'
  | 'REACTION_SENT';

@Injectable()
export class HeatmapService {
  private readonly logger = new Logger(HeatmapService.name);
  private readonly VELOCITY_WINDOW_SECONDS = 60; // Calculate velocity over the last 60 seconds

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly prisma: PrismaService,
  ) {}

  /**
   * Listens for any engagement event and tracks it for heatmap calculations.
   */
  @OnEvent('heatmap-events')
  async handleHeatmapEvent(payload: {
    sessionId: string;
    type: HeatmapEventType;
  }) {
    const metadata = await this._getSessionMetadata(payload.sessionId);
    if (!metadata) return;

    const eventKey = `heatmap:data:${metadata.eventId}`;
    const velocityKey = `heatmap:ts:${payload.type}:${payload.sessionId}`; // e.g., heatmap:ts:MESSAGE_SENT:session-123

    // Use a transaction to perform both operations atomically
    await this.redis
      .multi()
      // 1. Increment the total heat score for the session
      .hincrby(eventKey, payload.sessionId, 1)
      // 2. Add the event to our time-series sorted set
      .zadd(velocityKey, Date.now(), `${Date.now()}-${Math.random()}`)
      // Set an expiration on the keys so they auto-delete after the event
      .expire(eventKey, 3600 * 6) // 6 hours
      .expire(velocityKey, 3600 * 6)
      .exec();
  }

  /**
   * Fetches the complete heatmap data, including velocity, for an event.
   */
  async getHeatmapData(eventId: string) {
    const heatmapKey = `heatmap:data:${eventId}`;
    const [heatScores, sessions] = await Promise.all([
      this.redis.hgetall(heatmapKey),
      this.prisma.chatSession.findMany({
        where: { eventId },
        select: { id: true },
      }),
    ]);

    const sessionIds = sessions.map((s) => s.id);

    // Calculate velocities for each session
    const chatVelocities = await this._getVelocityForSessions(
      sessionIds,
      'MESSAGE_SENT',
    );
    const qnaVelocities = await this._getVelocityForSessions(
      sessionIds,
      'QUESTION_ASKED',
    );

    // Combine the data
    const heatmapData = {};
    for (const sessionId of sessionIds) {
      heatmapData[sessionId] = {
        heat: parseInt(heatScores[sessionId] || '0', 10),
        chatVelocity: chatVelocities[sessionId] || 0,
        qnaVelocity: qnaVelocities[sessionId] || 0,
      };
    }

    return {
      sessionHeat: heatmapData,
      updatedAt: new Date().toISOString(),
    };
  }

  /**
   * Calculates the per-minute velocity for a specific action across multiple sessions.
   */
  private async _getVelocityForSessions(
    sessionIds: string[],
    eventType: HeatmapEventType,
  ): Promise<Record<string, number>> {
    const pipeline = this.redis.multi();
    const now = Date.now();
    const oneMinuteAgo = now - this.VELOCITY_WINDOW_SECONDS * 1000;

    // Build a transaction to query all sessions at once
    for (const sessionId of sessionIds) {
      const velocityKey = `heatmap:ts:${eventType}:${sessionId}`;
      // 1. Remove all events older than our time window
      pipeline.zremrangebyscore(velocityKey, '-inf', oneMinuteAgo);
      // 2. Count the remaining events
      pipeline.zcard(velocityKey);
    }

    const results = await pipeline.exec();
    const velocities: Record<string, number> = {};

    // Process the results: each pair of results corresponds to one session
    if (results) {
      for (let i = 0; i < sessionIds.length; i++) {
        const sessionId = sessionIds[i];
        const zcardResult = results[i * 2 + 1]; // The result of the zcard command
        // zcardResult is [error, value]
        if (
          zcardResult &&
          !zcardResult[0] &&
          typeof zcardResult[1] === 'number'
        ) {
          velocities[sessionId] = zcardResult[1];
        } else {
          velocities[sessionId] = 0;
        }
      }
    } else {
      // If results is null, set all velocities to 0
      for (const sessionId of sessionIds) {
        velocities[sessionId] = 0;
      }
    }

    return velocities;
  }

  // This is our standard, robust pattern for fetching session metadata
  private async _getSessionMetadata(
    sessionId: string,
  ): Promise<SessionMetadata | null> {
    const redisKey = `session:info:${sessionId}`;
    const cachedData = await this.redis.get(redisKey);
    if (cachedData) {
      const parsedData: unknown = JSON.parse(cachedData);
      if (isSessionMetadata(parsedData)) {
        return parsedData;
      }
    }

    const sessionFromDb = await this.prisma.chatSession.findUnique({
      where: { id: sessionId },
      select: { eventId: true, organizationId: true },
    });

    if (sessionFromDb) {
      await this.redis.set(redisKey, JSON.stringify(sessionFromDb), 'EX', 3600);
      return sessionFromDb;
    }

    this.logger.warn(
      `Could not find metadata for session ${sessionId} for heatmap.`,
    );
    return null;
  }
}
