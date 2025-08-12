//src/live/dashboard/dashboard.gateway.ts
import {
  ConnectedSocket,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { ForbiddenException, forwardRef, Inject, Logger } from '@nestjs/common';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { DashboardService } from './dashboard.service';
import { CapacityUpdateDto } from './dto/capacity-update.dto';

/**
 * Gateway for real-time event dashboard updates.
 *
 * Usage:
 *  - Admin client sends 'dashboard.join' to start receiving live updates.
 *  - The eventId is provided via the WebSocket handshake query parameters, not in the message payload.
 *  - Gateway manages periodic dashboard data pushes every 5 seconds.
 */

// Define the new DTO shape here for clarity in the gateway
interface MultitenantMetricsDto {
  orgId: string;
  metrics: object;
}
@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class DashboardGateway {
  private readonly logger = new Logger(DashboardGateway.name);
  @WebSocketServer() server: Server;

  // Tracks active timers for event dashboard broadcasts
  private activeDashboardTimers = new Map<string, NodeJS.Timeout>();
  private readonly BROADCAST_INTERVAL = 5000; // Push updates every 5 seconds

  constructor(
    @Inject(forwardRef(() => DashboardService))
    private readonly dashboardService: DashboardService,
  ) {}

  /**
   * Admin client joins dashboard updates for an event.
   *
   * @param client - Connected WebSocket client socket.
   * @returns Object indicating success or error message.
   * @throws ForbiddenException if the user does not have permission to view the dashboard.
   * @throws Error if eventId is missing from the handshake query (returns error in response object).
   */
  @SubscribeMessage('dashboard.join')
  handleJoinDashboard(@ConnectedSocket() client: AuthenticatedSocket): {
    success: boolean;
    error?: string;
  } {
    const user = getAuthenticatedUser(client);
    const { eventId } = client.handshake.query as { eventId: string };

    const requiredPermission = 'dashboard:read:live';
    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to view this dashboard.',
      );
    }

    if (!eventId) {
      return {
        success: false,
        error: 'Event ID is required to join a dashboard.',
      };
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
   * Broadcasts a capacity update to the private admin dashboard room.
   */
  public broadcastCapacityUpdate(payload: CapacityUpdateDto) {
    const adminRoom = `dashboard:${payload.eventId}`;
    const eventName = 'dashboard.capacity.updated';
    this.server.to(adminRoom).emit(eventName, payload);
    this.logger.log(`Broadcasted capacity update to room ${adminRoom}`);
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
}
