import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  ConnectedSocket,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Inject, Logger, forwardRef } from '@nestjs/common';
import { MonetizationService } from './monetization.service';
import { AdContent } from 'src/common/interfaces/ad-content.interface';
import { OfferContent } from 'src/common/interfaces/offer-content.interface';
import { WaitlistService } from '../waitlist/waitlist.service';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';

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
  cors: { origin: '*', credentials: true },
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
    const eventRoom = `event:${adContent.eventId}`;
    const eventName = 'monetization.ad.injected';
    this.server.to(eventRoom).emit(eventName, adContent);
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
    const eventName = 'monetization.upsell.new';
    this.server.to(userRoom).emit(eventName, offerContent);
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
  async handleJoinWaitlist(@ConnectedSocket() client: AuthenticatedSocket) {
    const user = getAuthenticatedUser(client); // Decodes JWT to extract user info
    const { sessionId } = client.handshake.query as { sessionId: string };

    await this.waitlistService.addUserToWaitlist(sessionId, user.sub);

    return {
      success: true,
      message: 'You have been added to the waitlist.',
    };
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
  public sendWaitlistNotification(targetUserId: string, payload: any): void {
    const userRoom = `user:${targetUserId}`;
    const eventName = 'monetization.waitlist.spot_available';
    this.server.to(userRoom).emit(eventName, payload);
    this.logger.log(`Sent waitlist spot notification to user ${targetUserId}`);
  }
}
