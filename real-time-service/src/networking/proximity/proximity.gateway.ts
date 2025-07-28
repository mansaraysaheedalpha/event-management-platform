import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger } from '@nestjs/common';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { ProximityService } from './proximity.service';
import { UpdateLocationDto } from './dto/update-location.dto';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class ProximityGateway {
  private readonly logger = new Logger(ProximityGateway.name);
  @WebSocketServer() server: Server;

  constructor(private readonly proximityService: ProximityService) {}

  /**
   * Handles a user's location update.
   */
  @SubscribeMessage('proximity.location.update')
  async handleUpdateLocation(
    @MessageBody() dto: UpdateLocationDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      // 1. Update the user's location in Redis
      await this.proximityService.updateUserLocation(user.sub, dto);

      // 2. Find users nearby this user's new location
      const nearbyUserIds = await this.proximityService.findNearbyUsers(
        user.sub,
      );

      // 3. Send a personalized roster update back to the user who sent their location
      // In a more advanced system, we would also update the other nearby users.
      client.emit('proximity.roster.updated', { nearbyUserIds });

      return { success: true };
    } catch (error) {
      this.logger.error(
        `Failed to update location for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }
}
