//src/ops/heatmap/heatmap.service.ts
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

// Helper to check if a string looks like a technical ID (not a friendly name)
function isIdLikeName(name: string | null | undefined): boolean {
  if (!name || name.trim() === '') return true;
  // Check if it looks like a UUID (8-4-4-4-12 hex pattern)
  const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  // Check if it looks like a CUID (starts with 'c' followed by alphanumeric)
  const cuidPattern = /^c[a-z0-9]{20,}$/i;
  // Check if it looks like a prefixed ID (e.g., "ses_abc123", "session_xyz")
  const prefixedIdPattern = /^(ses|session|sess)_[a-z0-9]+$/i;
  return uuidPattern.test(name) || cuidPattern.test(name) || prefixedIdPattern.test(name);
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
   * Tracks both total engagement count AND unique engagers per session.
   */
  @OnEvent('heatmap-events')
  async handleHeatmapEvent(payload: {
    sessionId: string;
    userId?: string;
    type?: HeatmapEventType;
  }) {
    const metadata = await this._getSessionMetadata(payload.sessionId);
    if (!metadata) return;

    const heatKey = `heatmap:data:${metadata.eventId}`;
    const engagersKey = `heatmap:engagers:${payload.sessionId}`; // Set of unique user IDs
    const velocityKey = `heatmap:ts:${payload.type || 'UNKNOWN'}:${payload.sessionId}`;

    // Use a transaction to perform all operations atomically
    const multi = this.redis.multi();

    // 1. Increment the total heat score for the session
    multi.hincrby(heatKey, payload.sessionId, 1);

    // 2. Track unique engager (if userId provided)
    if (payload.userId) {
      multi.sadd(engagersKey, payload.userId);
      multi.expire(engagersKey, 3600 * 6); // 6 hours
    }

    // 3. Add the event to our time-series sorted set for velocity
    multi.zadd(velocityKey, Date.now(), `${Date.now()}-${Math.random()}`);

    // Set expirations
    multi.expire(heatKey, 3600 * 6);
    multi.expire(velocityKey, 3600 * 6);

    await multi.exec();
  }

  /**
   * Fetches the complete heatmap data, including velocity and unique engagers, for an event.
   */
  async getHeatmapData(eventId: string) {
    const heatmapKey = `heatmap:data:${eventId}`;
    const [heatScores, sessions] = await Promise.all([
      this.redis.hgetall(heatmapKey),
      this.prisma.chatSession.findMany({
        where: { eventId },
        select: { id: true, name: true },
      }),
    ]);

    const sessionIds = sessions.map((s) => s.id);

    // Build a pipeline to fetch velocities and unique engager counts
    const chatVelocities = await this._getVelocityForSessions(
      sessionIds,
      'MESSAGE_SENT',
    );
    const qnaVelocities = await this._getVelocityForSessions(
      sessionIds,
      'QUESTION_ASKED',
    );

    // Fetch unique engager counts for each session
    const uniqueEngagers = await this._getUniqueEngagerCounts(sessionIds);

    // Create a map of session names
    const sessionNames = new Map(sessions.map((s) => [s.id, s.name]));

    // Combine the data
    const heatmapData: Record<
      string,
      {
        heat: number;
        uniqueEngagers: number;
        chatVelocity: number;
        qnaVelocity: number;
        sessionName: string;
      }
    > = {};

    for (let i = 0; i < sessionIds.length; i++) {
      const sessionId = sessionIds[i];
      const rawName = sessionNames.get(sessionId);
      // Use a friendly name if the actual name looks like an ID
      const friendlyName = isIdLikeName(rawName)
        ? `Session ${i + 1}`
        : rawName;

      heatmapData[sessionId] = {
        heat: parseInt(heatScores[sessionId] || '0', 10),
        uniqueEngagers: uniqueEngagers[sessionId] || 0,
        chatVelocity: chatVelocities[sessionId] || 0,
        qnaVelocity: qnaVelocities[sessionId] || 0,
        sessionName: friendlyName!,
      };
    }

    return {
      sessionHeat: heatmapData,
      updatedAt: new Date().toISOString(),
    };
  }

  /**
   * Fetches unique engager counts for multiple sessions using Redis SCARD.
   */
  private async _getUniqueEngagerCounts(
    sessionIds: string[],
  ): Promise<Record<string, number>> {
    if (sessionIds.length === 0) return {};

    const pipeline = this.redis.multi();
    for (const sessionId of sessionIds) {
      pipeline.scard(`heatmap:engagers:${sessionId}`);
    }

    const results = await pipeline.exec();
    const counts: Record<string, number> = {};

    if (results) {
      for (let i = 0; i < sessionIds.length; i++) {
        const result = results[i];
        if (result && !result[0] && typeof result[1] === 'number') {
          counts[sessionIds[i]] = result[1];
        } else {
          counts[sessionIds[i]] = 0;
        }
      }
    }

    return counts;
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
