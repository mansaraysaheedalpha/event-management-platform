//src/monetization/sponsors/sponsors.gateway.ts
import {
  ConnectedSocket,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { ForbiddenException, Inject, Logger, forwardRef } from '@nestjs/common';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { SponsorsService } from './sponsors.service';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class SponsorsGateway {
  private readonly logger = new Logger(SponsorsGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    @Inject(forwardRef(() => SponsorsService))
    private readonly sponsorsService: SponsorsService,
  ) {}

  /**
   * Handles a sponsor client joining their private lead-capture room.
   */
  @SubscribeMessage('sponsor.leads.join')
  handleJoinLeadStream(@ConnectedSocket() client: AuthenticatedSocket) {
    const user = getAuthenticatedUser(client);
    // This permission should be granted to sponsor users
    const requiredPermission = 'sponsor:leads:read';

    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to view sponsor leads.',
      );
    }

    // The sponsorId should be part of the user's JWT payload
    const sponsorId = user.sponsorId; // Assuming sponsorId is in the JWT

    if (!sponsorId) {
      return { success: false, error: 'Sponsor ID not found in token.' };
    }

    const sponsorRoom = `sponsor:${sponsorId}`;
    void client.join(sponsorRoom);
    this.logger.log(
      `Sponsor user ${user.sub} joined lead stream for sponsor ${sponsorId}`,
    );

    return { success: true };
  }

  /**
   * Broadcasts a new lead to the specific sponsor's private room.
   */
  public broadcastNewLead(sponsorId: string, leadData: any) {
    const sponsorRoom = `sponsor:${sponsorId}`;
    const eventName = 'lead.captured.new';
    this.server.to(sponsorRoom).emit(eventName, leadData);
    this.logger.log(`Broadcasted new lead to sponsor room: ${sponsorRoom}`);
  }

  /**
   * Broadcasts a lead intent score update to the specific sponsor's private room.
   */
  public broadcastLeadIntentUpdate(sponsorId: string, intentData: any) {
    const sponsorRoom = `sponsor:${sponsorId}`;
    const eventName = 'lead.intent.updated'; // As per the spec
    this.server.to(sponsorRoom).emit(eventName, intentData);
    this.logger.log(
      `Broadcasted lead intent update to sponsor room: ${sponsorRoom}`,
    );
  }
}
