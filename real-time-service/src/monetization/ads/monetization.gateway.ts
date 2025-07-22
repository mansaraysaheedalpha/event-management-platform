import { WebSocketGateway, WebSocketServer } from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Inject, Logger, forwardRef } from '@nestjs/common';
import { MonetizationService } from './monetization.service';
import { AdContent } from 'src/common/interfaces/ad-content.interface';
import { OfferContent } from 'src/common/interfaces/offer-content.interface';
import { WaitlistService } from '../waitlist/waitlist.service';
import { SubscribeMessage, ConnectedSocket } from '@nestjs/websockets';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class MonetizationGateway {
  private readonly logger = new Logger(MonetizationGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    @Inject(forwardRef(() => MonetizationService))
    private readonly monetizationService: MonetizationService,
    private readonly waitlistService: WaitlistService,
  ) {}

  public broadcastAd(adContent: AdContent) {
    const eventRoom = `event:${adContent.eventId}`;
    const eventName = 'monetization.ad.injected';
    this.server.to(eventRoom).emit(eventName, adContent);
    this.logger.log(`Broadcasted ad ${adContent.id} to room: ${eventRoom}`);
  }

  // NEW: Method to send an offer to a specific user
  public sendUpsellToUser(targetUserId: string, offerContent: OfferContent) {
    const userRoom = `user:${targetUserId}`;
    const eventName = 'monetization.upsell.new';
    this.server.to(userRoom).emit(eventName, offerContent);
    this.logger.log(
      `Sent upsell offer ${offerContent.id} to user ${targetUserId}`,
    );
  }

  // NEW: Handler for users joining a waitlist
  @SubscribeMessage('monetization.waitlist.join')
  async handleJoinWaitlist(@ConnectedSocket() client: AuthenticatedSocket) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };
    await this.waitlistService.addUserToWaitlist(sessionId, user.sub);
    return { success: true, message: 'You have been added to the waitlist.' };
  }

  // NEW: Method to send the notification to the user who is next in line
  public sendWaitlistNotification(targetUserId: string, payload: any) {
    const userRoom = `user:${targetUserId}`;
    const eventName = 'monetization.waitlist.spot_available';
    this.server.to(userRoom).emit(eventName, payload);
    this.logger.log(`Sent waitlist spot notification to user ${targetUserId}`);
  }
}
