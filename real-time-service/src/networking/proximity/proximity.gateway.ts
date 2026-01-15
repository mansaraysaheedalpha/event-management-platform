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
import { ConnectionsService } from '../connections/connections.service';
import { MatchingService } from '../matching/matching.service';
import { ConnectionType } from '@prisma/client';

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
    private readonly connectionsService: ConnectionsService,
    private readonly matchingService: MatchingService,
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

      // 2. Find users nearby this user's new location (scoped to this event)
      const nearbyUserIds = await this.proximityService.findNearbyUsers(
        user.sub,
        dto.eventId || '',
      );

      // 3. If eventId is provided, use matching service for enhanced context
      if (dto.eventId && nearbyUserIds.length > 0) {
        const enhancedUsers = await this.matchingService.getEnhancedNearbyUsers(
          user.sub,
          nearbyUserIds,
          dto.eventId,
        );

        // Format for compatibility with existing frontend
        const nearbyUsers = enhancedUsers.map((eu) => ({
          user: {
            id: eu.id,
            name: eu.name,
            avatarUrl: eu.avatarUrl,
          },
          distance: eu.distance,
          sharedInterests: [], // Keep for backward compatibility
          connectionContexts: eu.connectionContexts,
          matchScore: eu.matchScore,
          alreadyConnected: eu.alreadyConnected,
        }));

        client.emit('proximity.roster.updated', { nearbyUsers });
        return { success: true };
      }

      // 4. Fallback: Fetch basic user details for all nearby users
      const nearbyUserDetails = await this.prisma.userReference.findMany({
        where: { id: { in: nearbyUserIds } },
        select: {
          id: true,
          firstName: true,
          lastName: true,
          avatarUrl: true,
        },
      });

      // 5. Build basic roster with user details
      const nearbyUsers = nearbyUserIds.map((id) => {
        const userRef = nearbyUserDetails.find((u) => u.id === id);
        const name = userRef
          ? `${userRef.firstName || ''} ${userRef.lastName || ''}`.trim() ||
            'Attendee'
          : 'Attendee';
        return {
          user: {
            id,
            name,
            avatarUrl: userRef?.avatarUrl || undefined,
          },
          distance: undefined,
          sharedInterests: [],
        };
      });

      // 6. Send the roster update
      client.emit('proximity.roster.updated', { nearbyUsers });

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

    // Fetch the sender's name from our local UserReference table.
    const senderDetails = await this.prisma.userReference.findUnique({
      where: { id: sender.sub },
      select: { firstName: true, lastName: true },
    });

    const senderName = `${senderDetails?.firstName || 'An'} ${senderDetails?.lastName || 'Attendee'}`;

    const pingPayload = {
      fromUser: {
        id: sender.sub,
        name: senderName,
      },
      message: dto.message || `Hey! I see you're nearby.`,
      eventId: dto.eventId,
    };

    const targetUserRoom = `user:${dto.targetUserId}`;
    const eventName = 'proximity.ping.received';

    this.server.to(targetUserRoom).emit(eventName, pingPayload);

    // Create a connection record for this ping (with deduplication)
    try {
      // Check if a ping connection already exists within the last 5 minutes
      // to prevent duplicate records from repeated pings
      const recentPingCutoff = new Date(Date.now() - 5 * 60 * 1000);
      const existingConnection = await this.prisma.connection.findFirst({
        where: {
          userAId: sender.sub,
          userBId: dto.targetUserId,
          connectionType: ConnectionType.PROXIMITY_PING,
          connectedAt: {
            gte: recentPingCutoff,
          },
        },
      });

      if (!existingConnection) {
        await this.connectionsService.createConnection({
          userAId: sender.sub,
          userBId: dto.targetUserId,
          eventId: dto.eventId,
          connectionType: ConnectionType.PROXIMITY_PING,
          initialMessage: dto.message,
        });
        this.logger.log(
          `Created connection record for proximity ping from ${sender.sub} to ${dto.targetUserId}`,
        );
      } else {
        this.logger.log(
          `Skipping duplicate connection record - recent ping exists from ${sender.sub} to ${dto.targetUserId}`,
        );
      }
    } catch (error) {
      // Don't fail the ping if connection tracking fails
      this.logger.error(
        `Failed to create connection record: ${getErrorMessage(error)}`,
      );
    }

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
