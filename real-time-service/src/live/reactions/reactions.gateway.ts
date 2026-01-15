//src/live/reactions/reactions.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger, Inject, forwardRef } from '@nestjs/common';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { ReactionsService } from './reactions.service';
import { SendReactionDto } from './dto/send-reactions.dto';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { EventRegistrationValidationService } from 'src/shared/services/event-registration-validation.service';

/**
 * Gateway to handle real-time emoji reactions in a session.
 *
 * Emits periodic 'reaction.burst' messages with the count of each emoji.
 *
 * @example
 * // Client emits a reaction:
 * socket.emit('reaction.send', { emoji: '🔥' });
 *
 * // Server emits burst update:
 * socket.on('reaction.burst', (payload) => { console.log(payload); });
 */
@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class ReactionsGateway {
  private readonly logger = new Logger(ReactionsGateway.name);
  @WebSocketServer() server: Server;

  private activeTimers = new Map<string, NodeJS.Timeout>();
  private readonly BROADCAST_INTERVAL = 2000; // 2 seconds

  constructor(
    @Inject(forwardRef(() => ReactionsService))
    private readonly reactionsService: ReactionsService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly eventRegistrationValidationService: EventRegistrationValidationService,
  ) {}

  /**
   * Handles incoming reaction from user and schedules broadcasting.
   * Validates that the user is registered for the event before accepting reactions.
   *
   * @param dto The payload containing the emoji reaction.
   * @param client The authenticated WebSocket client.
   */
  @SubscribeMessage('reaction.send')
  async handleSendReaction(
    @MessageBody() dto: SendReactionDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ): Promise<void> {
    const { sessionId } = client.handshake.query as { sessionId: string };
    const user = getAuthenticatedUser(client);
    const userId = user.sub;

    if (!sessionId) return;

    // Get eventId from query params (defaults to sessionId if not provided)
    const eventId = (client.handshake.query.eventId as string) || sessionId;

    // Validate event registration
    const isRegistered =
      await this.eventRegistrationValidationService.isUserRegistered(
        userId,
        eventId,
      );
    if (!isRegistered) {
      this.logger.warn(
        `[Reactions] User ${userId} denied - not registered for event ${eventId}`,
      );
      client.emit('reaction.error', {
        message: 'You are not registered for this event.',
        statusCode: 403,
      });
      return;
    }

    await this.reactionsService.addReaction(sessionId, userId, dto.emoji);

    if (!this.activeTimers.has(sessionId)) {
      this.logger.log(
        `Starting reaction broadcast loop for session: ${sessionId}`,
      );
      this.scheduleNextBroadcast(sessionId);
    }
  }

  /**
   * Schedules the next broadcast cycle for a session.
   *
   * @param sessionId The session identifier.
   * @returns {void}
   */
  private scheduleNextBroadcast(sessionId: string): void {
    const timer = setTimeout(() => {
      this.runBroadcastCycle(sessionId).catch((err) =>
        this.logger.error(
          `Unhandled error in broadcast cycle for session ${sessionId}: ${getErrorMessage(err)}`,
        ),
      );
    }, this.BROADCAST_INTERVAL);
    this.activeTimers.set(sessionId, timer);
  }

  /**
   * Runs a broadcast cycle: fetches reactions from Redis and emits to clients.
   *
   * @param sessionId The session identifier.
   * @returns {Promise<void>}
   */
  private async runBroadcastCycle(sessionId: string): Promise<void> {
    try {
      const redisKey = `reactions:${sessionId}`;

      const results = await this.redis
        .multi()
        .hgetall(redisKey)
        .del(redisKey)
        .exec();

      if (!results) {
        this.logger.warn(
          `Redis transaction for session ${sessionId} failed and returned null.`,
        );
        return;
      }

      // Detect command-level failures
      const [hgetAllErr, rawCounts] = results[0];
      if (hgetAllErr) {
        this.logger.error(
          `Redis hgetall error for session ${sessionId}: ${getErrorMessage(hgetAllErr)}`,
        );
        return;
      }

      const reactionCounts = rawCounts as Record<string, string>;

      if (!reactionCounts || Object.keys(reactionCounts).length === 0) {
        this.stopBroadcastingForSession(sessionId);
        return;
      }

      const payload = Object.entries(reactionCounts).reduce(
        (acc, [emoji, count]) => {
          acc[emoji] = parseInt(count, 10);
          return acc;
        },
        {} as Record<string, number>,
      );

      const publicRoom = `session:${sessionId}`;
      this.server.to(publicRoom).emit('reaction.burst', payload);
    } catch (error) {
      this.logger.error(
        `Failed to broadcast reactions for session ${sessionId}: ${getErrorMessage(error)}`,
      );
    } finally {
      if (this.activeTimers.has(sessionId)) {
        this.scheduleNextBroadcast(sessionId);
      }
    }
  }

  /**
   * Stops broadcasting loop for a session when there are no more reactions.
   *
   * @param sessionId The session identifier.
   * @returns {void}
   */
  private stopBroadcastingForSession(sessionId: string): void {
    if (this.activeTimers.has(sessionId)) {
      this.logger.log(
        `Stopping reaction broadcast loop for session: ${sessionId}`,
      );
      const timer = this.activeTimers.get(sessionId);
      clearTimeout(timer);
      this.activeTimers.delete(sessionId);
    }
  }

  /**
   * Broadcasts the latest mood analytics to all attendees in a session.
   * This is a public method called by the ReactionsService.
   */
  public broadcastMoodAnalytics(sessionId: string, analyticsPayload: any) {
    const publicRoom = `session:${sessionId}`;
    const eventName = 'mood.analytics.updated'; // A more specific event name
    this.server.to(publicRoom).emit(eventName, analyticsPayload);
    this.logger.log(`Broadcasted mood analytics to room ${publicRoom}`);
  }
}
