import {
  ConnectedSocket,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { ForbiddenException, Logger } from '@nestjs/common';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { DashboardService } from './dashboard.service';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class DashboardGateway {
  private readonly logger = new Logger(DashboardGateway.name);
  @WebSocketServer() server: Server;

  // We keep track of active broadcast timers for each event's dashboard
  private activeDashboardTimers = new Map<string, NodeJS.Timeout>();
  private readonly BROADCAST_INTERVAL = 5000; // Push updates every 5 seconds

  constructor(private readonly dashboardService: DashboardService) {}

  /**
   * An admin client sends this event to start receiving dashboard updates.
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

  private scheduleNextBroadcast(eventId: string) {
    const timer = setTimeout(() => {
      void this.runBroadcastCycle(eventId);
    }, this.BROADCAST_INTERVAL);
    this.activeDashboardTimers.set(eventId, timer);
  }

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

  private stopBroadcastingForEvent(eventId: string) {
    if (this.activeDashboardTimers.has(eventId)) {
      const timer = this.activeDashboardTimers.get(eventId);
      clearTimeout(timer);
      this.activeDashboardTimers.delete(eventId);
    }
  }
}
