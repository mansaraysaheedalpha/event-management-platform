//src/monetization/ads/monetization.gateway.ts
/**
 * Interface describing the payload for waitlist spot notifications.
 */

function assertValidRoomId(eventId: string): void {
  // Only allow alphanumeric, dash, and underscore
  if (!/^[\w-]+$/.test(eventId)) {
    throw new Error(`Invalid eventId for room: ${eventId}`);
  }
}
import { getErrorMessage } from 'src/common/utils/error.utils';
import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  ConnectedSocket,
  MessageBody,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Inject, Logger, forwardRef } from '@nestjs/common';
import { MonetizationService } from './monetization.service';
import { AdContent } from 'src/common/interfaces/ad-content.interface';
import { OfferContent } from 'src/common/interfaces/offer-content.interface';
import { WaitlistService } from '../waitlist/waitlist.service';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { WaitlistNotificationPayload } from 'src/common/interfaces/monetization.interface';
import { MONETIZATION_EVENTS } from '../monetization.events';

/**
 * WebSocket Gateway handling real-time monetization events.
 *
 * - Ads are pushed to all users in a specific event room.
 * - Upsell offers are sent directly to individual users.
 * - Waitlist join requests are received from clients.
 * - Notifications are pushed to users when their waitlist spot is available.
 *
 * Gateway listens on namespace `/events` and allows cross-origin access.
 *
 * ## Usage Examples:
 * - Client joins room: `socket.join('event:abc123')`
 * - Server sends ad to all in event: `broadcastAd({ eventId: 'abc123', ... })`
 * - Server sends upsell: `sendUpsellToUser('user-1', { ... })`
 * - Client emits: `'monetization.waitlist.join'`
 */
@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class MonetizationGateway {
  /** Logger specific to this gateway */
  private readonly logger = new Logger(MonetizationGateway.name);

  /** Raw Socket.IO server instance injected by NestJS */
  @WebSocketServer() server: Server;

  constructor(
    /**
     * MonetizationService contains business logic like tracking ad engagement.
     * Using forwardRef to avoid circular dependency issues.
     */
    @Inject(forwardRef(() => MonetizationService))
    private readonly monetizationService: MonetizationService,

    /** Handles waitlist management (add, notify, remove) */
    private readonly waitlistService: WaitlistService,
  ) {}

  /**
   * Broadcasts an advertisement to all users in a specific event room.
   * This is useful for showing sponsor ads or messages to all attendees.
   *
   * @param adContent - Details of the ad (must include eventId)
   *
   * @example
   * broadcastAd({
   *   id: 'ad-1',
   *   eventId: 'evt-123',
   *   title: '50% off drinks!',
   *   imageUrl: 'https://cdn.ads.com/drinks.png',
   * });
   */
  public broadcastAd(adContent: AdContent): void {
    try {
      assertValidRoomId(adContent.eventId);
    } catch (err) {
      const msg = getErrorMessage(err);
      this.logger.warn(`Ad broadcast aborted: ${msg}`);
      return;
    }
    const eventRoom = `event:${adContent.eventId}`;
    this.server.to(eventRoom).emit(MONETIZATION_EVENTS.AD_INJECTED, adContent);
    this.logger.log(`Broadcasted ad ${adContent.id} to room: ${eventRoom}`);
  }

  /**
   * Sends a personalized upsell offer to a single user.
   * Useful for promoting VIP upgrades or premium features.
   *
   * @param targetUserId - User ID to target (client must be in `user:<id>` room)
   * @param offerContent - Offer details (title, description, price, etc.)
   *
   * @example
   * sendUpsellToUser('user-101', {
   *   id: 'offer-1',
   *   title: 'Upgrade to VIP',
   *   description: 'Enjoy front-row seating and free drinks',
   *   price: 49.99,
   * });
   */
  public sendUpsellToUser(
    targetUserId: string,
    offerContent: OfferContent,
  ): void {
    const userRoom = `user:${targetUserId}`;
    this.server.to(userRoom).emit(MONETIZATION_EVENTS.UPSELL_NEW, offerContent);
    this.logger.log(
      `Sent upsell offer ${offerContent.id} to user ${targetUserId}`,
    );
  }

  /**
   * Handles client request to join a waitlist for a session.
   * Called when client emits: `monetization.waitlist.join`
   *
   * The method:
   * - Authenticates the user from the socket
   * - Extracts the session ID from the handshake query
   * - Adds the user to the waitlist via WaitlistService
   *
   * @param client - The connected, authenticated WebSocket client
   * @returns A success message to the client
   *
   * @example
   * socket.emit('monetization.waitlist.join');
   */
  @SubscribeMessage('monetization.waitlist.join')
  async handleJoinWaitlist(
    @MessageBody() dto: { idempotencyKey: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ): Promise<{ success: boolean; message?: string; error?: string }> {
    let user: { sub?: string } | undefined;
    try {
      user = getAuthenticatedUser(client);
    } catch (err) {
      this.logger.warn('Failed to authenticate user for waitlist join', err);
      return {
        success: false,
        error: 'Authentication failed. Please re-login.',
      };
    }

    const { sessionId } = client.handshake.query as { sessionId?: string };
    if (!sessionId) {
      return {
        success: false,
        error: 'Session ID is required to join the waitlist.',
      };
    }
    if (!user?.sub || typeof user.sub !== 'string') {
      return {
        success: false,
        error: 'User ID is missing or invalid.',
      };
    }

    // HR2: Validate idempotencyKey to prevent replay without proper key
    if (!dto?.idempotencyKey || typeof dto.idempotencyKey !== 'string') {
      return {
        success: false,
        error: 'Idempotency key is required.',
      };
    }

    try {
      await this.waitlistService.addUserToWaitlist(
        sessionId,
        user.sub,
        dto.idempotencyKey,
      );
      return {
        success: true,
        message: 'You have been added to the waitlist.',
      };
    } catch (err) {
      this.logger.error('Failed to add user to waitlist', err);
      return {
        success: false,
        error: 'Failed to add user to waitlist. Please try again later.',
      };
    }
  }

  /**
   * Notifies a user when a waitlist spot becomes available.
   * Typically triggered when someone cancels or leaves a session.
   *
   * @param targetUserId - ID of the user to notify
   * @param payload - Custom notification payload
   *
   * @example
   * sendWaitlistNotification('user-202', {
   *   sessionId: 's-99',
   *   message: 'A spot just opened up! Join now.',
   * });
   */
  public sendWaitlistNotification(
    targetUserId: string,
    payload: WaitlistNotificationPayload,
  ): void {
    const userRoom = `user:${targetUserId}`;
    this.server.to(userRoom).emit(MONETIZATION_EVENTS.WAITLIST_OFFER, payload);
    this.logger.log(`Sent waitlist spot notification to user ${targetUserId}`);
  }

  /**
   * Notifies users in a waitlist about their updated position.
   * Useful for showing queue status in real-time.
   *
   * @param userIds - Array of user IDs to notify with their positions
   * @param sessionId - The session ID for the waitlist
   * @param totalInQueue - Total number of users in the queue
   *
   * @example
   * sendWaitlistPositionUpdate([
   *   { userId: 'user-1', position: 1 },
   *   { userId: 'user-2', position: 2 }
   * ], 's-99', 5);
   */
  public sendWaitlistPositionUpdate(
    userIds: Array<{ userId: string; position: number }>,
    sessionId: string,
    totalInQueue: number,
    estimatedWaitMinutes?: number,
  ): void {
    userIds.forEach(({ userId, position }) => {
      const userRoom = `user:${userId}`;
      const payload = {
        position,
        total: totalInQueue,
        estimated_wait_minutes: estimatedWaitMinutes || Math.ceil(position * 2),
        session_id: sessionId,
      };
      this.server.to(userRoom).emit(MONETIZATION_EVENTS.WAITLIST_POSITION_UPDATE, payload);
    });
    this.logger.log(
      `Sent position updates to ${userIds.length} users in session ${sessionId}`,
    );
  }

  /**
   * Notifies a user when their waitlist offer has expired.
   * Triggered when the user doesn't accept the offer within the time limit.
   *
   * @param targetUserId - ID of the user to notify
   * @param sessionId - The session ID for the waitlist
   * @param message - Custom expiration message
   *
   * @example
   * sendWaitlistOfferExpired('user-202', 's-99', 'Your spot offer has expired.');
   */
  public sendWaitlistOfferExpired(
    targetUserId: string,
    sessionId: string,
    message: string,
  ): void {
    const userRoom = `user:${targetUserId}`;
    const payload = {
      message,
      session_id: sessionId,
    };
    this.server.to(userRoom).emit(MONETIZATION_EVENTS.WAITLIST_OFFER_EXPIRED, payload);
    this.logger.log(`Sent offer expiration notification to user ${targetUserId}`);
  }
}
