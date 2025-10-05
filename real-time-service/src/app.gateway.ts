// src/app.gateway.ts
import {
  ConnectedSocket,
  OnGatewayConnection,
  OnGatewayDisconnect,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import {
  forwardRef,
  Inject,
  Logger,
  OnApplicationShutdown,
} from '@nestjs/common';
import {
  AuthenticatedSocket,
  JwtPayload,
} from './common/interfaces/auth.interface';
import { ConnectionService } from './system/connection/connection.service';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { getErrorMessage } from './common/utils/error.utils';
import {
  extractTokenSafely,
  getAuthenticatedUser,
} from './common/utils/auth.utils';
import { Server } from 'socket.io';
import { DashboardService } from './live/dashboard/dashboard.service';
import { OnEvent } from '@nestjs/event-emitter';
import { CapacityUpdateDto } from './live/dashboard/dto/capacity-update.dto';

// Define the new DTO shape here for clarity in the gateway
interface MultitenantMetricsDto {
  orgId: string;
  metrics: object;
}
@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class AppGateway
  implements OnGatewayConnection, OnGatewayDisconnect, OnApplicationShutdown
{
  @WebSocketServer()
  server: Server;

  private readonly logger = new Logger('AppGateway');

  // Tracks active timers for event dashboard broadcasts
  private activeDashboardTimers = new Map<string, NodeJS.Timeout>();
  private readonly BROADCAST_INTERVAL = 5000; // Push updates every 5 seconds

  constructor(
    private readonly connectionService: ConnectionService,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
    @Inject(forwardRef(() => DashboardService))
    private readonly dashboardService: DashboardService,
  ) {}

  afterInit(server: Server) {
    // Increased listeners to prevent warnings during rapid client reconnects.
    server.setMaxListeners(30);
    this.logger.log('AppGateway initialized and max listeners set.');
  }

  private handleError(client: AuthenticatedSocket, error: unknown) {
    const errorMessage = getErrorMessage(error);
    this.logger.error(`🔴 Auth error for client ${client.id}: ${errorMessage}`);
    client.emit('systemError', {
      message: 'Authentication failed.',
      reason: errorMessage,
    });
    client.disconnect(true);
  }

  async handleConnection(client: AuthenticatedSocket) {
    try {
      const token = extractTokenSafely(client);

      if (!token) {
        return this.handleError(
          client,
          new Error('Missing authentication token.'),
        );
      }

      const payload = this.jwtService.verify<JwtPayload>(token, {
        secret: this.configService.getOrThrow<string>('JWT_SECRET'),
      });
      client.data.user = payload;

      await client.join(`user:${payload.sub}`);
      this.logger.log(
        `✅ Client Connected: ${client.id} | User: ${payload.email}`,
      );
      client.emit('connectionAcknowledged', { userId: payload.sub });
      this.connectionService.startHeartbeat(client);
    } catch (error) {
      this.handleError(client, error);
    }
  }

  handleDisconnect(client: AuthenticatedSocket) {
    this.logger.log(`❌ Client Disconnected: ${client.id}`);
    this.connectionService.stopHeartbeat(client.id);
  }

  /**
   * Admin client joins dashboard updates for an event.
   *
   * @param client - Connected WebSocket client socket.
   * @returns Object indicating success or error message.
   */
  @SubscribeMessage('dashboard.join')
  handleJoinDashboard(@ConnectedSocket() client: AuthenticatedSocket): {
    success: boolean;
    error?: string;
  } {
    const user = getAuthenticatedUser(client);
    const { eventId } = client.handshake.query as { eventId: string };
    this.logger.log(
      `Received dashboard.join from user ${user.sub} for event ${eventId}`,
    );

    const requiredPermission = 'dashboard:read:live';
    if (!user.permissions?.includes(requiredPermission)) {
      const errorMsg = 'You do not have permission to view this dashboard.';
      this.logger.warn(
        `Dashboard join failed for user ${user.sub}: ${errorMsg}`,
      );
      return { success: false, error: errorMsg };
    }

    if (!eventId) {
      const errorMsg = 'Event ID is required to join a dashboard.';
      this.logger.warn(
        `Dashboard join failed for user ${user.sub}: ${errorMsg}`,
      );
      return { success: false, error: errorMsg };
    }

    const dashboardRoom = `dashboard:${eventId}`;
    void client.join(dashboardRoom);
    this.logger.log(`Admin ${user.sub} joined dashboard for event ${eventId}`);

    // If this is the first admin to join, start the broadcast loop for this event.
    if (!this.activeDashboardTimers.has(eventId)) {
      this.logger.log(
        `Starting dashboard broadcast loop for event: ${eventId}`,
      );
      this.scheduleNextBroadcast(eventId);
    }

    return { success: true };
  }

  /**
   * Schedule the next broadcast cycle for the event dashboard.
   *
   * @param eventId - ID of the event.
   */
  private scheduleNextBroadcast(eventId: string) {
    const timer = setTimeout(() => {
      void this.runBroadcastCycle(eventId);
    }, this.BROADCAST_INTERVAL);
    this.activeDashboardTimers.set(eventId, timer);
  }

  /**
   * Runs one cycle of fetching dashboard data and broadcasting to clients.
   *
   * Stops if no clients are listening.
   *
   * @param eventId - ID of the event.
   * @returns Promise<void>
   */
  private async runBroadcastCycle(eventId: string) {
    const dashboardRoom = `dashboard:${eventId}`;

    // Check if anyone is still listening before we do the work.
    const room = this.server.sockets.adapter.rooms.get(dashboardRoom);
    if (!room || room.size === 0) {
      this.logger.log(
        `No admins listening; stopping dashboard loop for event: ${eventId}`,
      );
      this.stopBroadcastingForEvent(eventId);
      return;
    }

    try {
      const dashboardData =
        await this.dashboardService.getDashboardData(eventId);
      this.server.to(dashboardRoom).emit('dashboard.update', dashboardData);
    } catch (error) {
      this.logger.error(
        `Failed to fetch or broadcast dashboard data for event ${eventId}`,
        error,
      );
    } finally {
      // If the timer hasn't been stopped, schedule the next run.
      if (this.activeDashboardTimers.has(eventId)) {
        this.scheduleNextBroadcast(eventId);
      }
    }
  }

  /**
   * Stops broadcasting dashboard updates for an event.
   *
   * @param eventId - ID of the event.
   * @returns void
   */
  private stopBroadcastingForEvent(eventId: string) {
    if (this.activeDashboardTimers.has(eventId)) {
      const timer = this.activeDashboardTimers.get(eventId);
      clearTimeout(timer);
      this.activeDashboardTimers.delete(eventId);
    }
  }

  /**
   * Listens for capacity update events and triggers a broadcast.
   */
  @OnEvent('capacity-events')
  handleCapacityUpdate(payload: CapacityUpdateDto) {
    this.logger.log(
      `Processing capacity update for resource: ${payload.resourceId}`,
    );
    this.broadcastCapacityUpdate(payload);
  }

  /**
   * Broadcasts a capacity update to the private admin dashboard room.
   */
  public broadcastCapacityUpdate(payload: CapacityUpdateDto) {
    const adminRoom = `dashboard:${payload.eventId}`;
    const eventName = 'dashboard.capacity.updated';
    this.server.to(adminRoom).emit(eventName, payload);
    this.logger.log(`Broadcasted capacity update to room ${adminRoom}`);
  }

  /**
   * Listens for system-wide metric events, finds all active events for the org,
   * and triggers a broadcast to all relevant dashboards.
   */
  @OnEvent('system-metrics-events')
  async handleSystemMetrics(payload: MultitenantMetricsDto) {
    this.logger.log(`Processing system metrics for org: ${payload.orgId}`);

    // 1. Get the list of all active event IDs for this organization from Redis.
    const activeEventIds = await this.dashboardService.getActiveEventIdsForOrg(
      payload.orgId,
    );

    if (activeEventIds.length === 0) {
      this.logger.log(
        `No active event dashboards for org ${payload.orgId}. Skipping broadcast.`,
      );
      return;
    }

    this.broadcastSystemMetrics(activeEventIds, payload);
  }

  /**
   * Broadcasts system-wide multitenant metrics to all active event dashboards for an organization.
   */
  public broadcastSystemMetrics(
    eventIds: string[],
    payload: MultitenantMetricsDto,
  ) {
    const eventName = 'dashboard.metrics.updated';

    // Loop through each active event and broadcast to its specific dashboard room.
    for (const eventId of eventIds) {
      const adminRoom = `dashboard:${eventId}`;
      this.server.to(adminRoom).emit(eventName, payload);
    }

    this.logger.log(
      `Broadcasted system metrics to ${eventIds.length} dashboards for org ${payload.orgId}`,
    );
  }

  /**
   * Called when the application is shutting down.
   * Clears any active timers to prevent resource leaks.
   */
  onApplicationShutdown() {
    this.logger.log(
      `Clearing ${this.activeDashboardTimers.size} active dashboard timers.`,
    );
    this.activeDashboardTimers.forEach((timer) => {
      clearTimeout(timer);
    });
    this.activeDashboardTimers.clear();
  }
}
