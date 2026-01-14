//src/networking/proximity/proximity.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger } from '@nestjs/common';
import { Throttle } from '@nestjs/throttler';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { ProximityService } from './proximity.service';
import { UpdateLocationDto } from './dto/update-location.dto';
import { ProximityPingDto } from './dto/proximity-ping.dto';
import { PrismaService } from 'src/prisma.service';
import { OnEvent } from '@nestjs/event-emitter';

// Define the shape of the payload we expect from the Oracle AI
interface ProximityUpdateDto {
  userId: string;
  nearbyUsers: {
    user: { id: string; name: string; avatarUrl?: string };
    distance: number;
    sharedInterests: string[];
  }[];
}

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class ProximityGateway {
  private readonly logger = new Logger(ProximityGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    private readonly proximityService: ProximityService,
    private readonly prisma: PrismaService,
  ) {}

  /**
   * Handles a user's location update.
   * Rate limited to 30 requests per minute to prevent abuse.
   */
  @Throttle({ default: { limit: 30, ttl: 60000 } })
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

  /**
   * Handles a user sending a "ping" to another nearby user.
   * Rate limited to 10 pings per minute to prevent harassment.
   */
  @Throttle({ default: { limit: 10, ttl: 60000 } })
  @SubscribeMessage('proximity.ping')
  async handleProximityPing(
    @MessageBody() dto: ProximityPingDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const sender = getAuthenticatedUser(client);

    // --- THIS IS THE FIX ---
    // Fetch the sender's name from our local UserReference table.
    const senderDetails = await this.prisma.userReference.findUnique({
      where: { id: sender.sub },
      select: { firstName: true, lastName: true },
    });

    const senderName = `${senderDetails?.firstName || 'An'} ${senderDetails?.lastName || 'Attendee'}`;
    // --- END OF FIX ---

    const pingPayload = {
      fromUser: {
        id: sender.sub,
        name: senderName,
      },
      message: dto.message || `Hey! I see you're nearby.`,
    };

    const targetUserRoom = `user:${dto.targetUserId}`;
    const eventName = 'proximity.ping.received';

    // Debug: Check room membership
    const adapter = this.server?.sockets?.adapter;
    if (!adapter) {
      this.logger.error('Server adapter is not available!');
    } else {
      const allRooms = Array.from(adapter.rooms.keys()).filter(
        (r) => r.startsWith('user:'),
      );
      this.logger.log(`All user rooms: ${JSON.stringify(allRooms)}`);
    }

    // Check how many sockets are in the target room
    const socketsInRoom = adapter?.rooms?.get(targetUserRoom);
    const socketCount = socketsInRoom ? socketsInRoom.size : 0;

    this.logger.log(
      `Emitting ping to room "${targetUserRoom}" | from: ${sender.sub} | sockets in room: ${socketCount} | payload: ${JSON.stringify(pingPayload)}`,
    );

    this.server.to(targetUserRoom).emit(eventName, pingPayload);

    this.logger.log(
      `Sent proximity ping from ${sender.sub} to ${dto.targetUserId}`,
    );

    return { success: true };
  }

  /**
   * Listens for internal proximity updates from the AI service and broadcasts them.
   */
  @OnEvent('proximity-updates')
  handleProximityUpdate(payload: ProximityUpdateDto) {
    const targetUserRoom = `user:${payload.userId}`;
    const eventName = 'proximity.roster.updated';

    this.server.to(targetUserRoom).emit(eventName, payload);
    this.logger.log(
      `Broadcasted advanced proximity roster to user ${payload.userId}`,
    );
  }
}
