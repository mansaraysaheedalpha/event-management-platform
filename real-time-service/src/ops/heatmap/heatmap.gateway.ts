//src/ops/heatmap/heatmap.gateway.ts
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
import { HeatmapService } from './heatmap.service';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class HeatmapGateway {
  private readonly logger = new Logger(HeatmapGateway.name);
  @WebSocketServer() server: Server;

  private activeHeatmapTimers = new Map<string, NodeJS.Timeout>();
  private readonly BROADCAST_INTERVAL = 5000; // Push updates every 5 seconds

  constructor(private readonly heatmapService: HeatmapService) {}

  @SubscribeMessage('heatmap.join')
  handleJoinHeatmap(@ConnectedSocket() client: AuthenticatedSocket) {
    const user = getAuthenticatedUser(client);
    const { eventId } = client.handshake.query as { eventId: string };
    const requiredPermission = 'heatmap:read';

    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to view the event heatmap.',
      );
    }

    const heatmapRoom = `heatmap:${eventId}`;
    void client.join(heatmapRoom);
    this.logger.log(`Admin ${user.sub} joined heatmap for event ${eventId}`);

    if (!this.activeHeatmapTimers.has(eventId)) {
      this.logger.log(`Starting heatmap broadcast loop for event: ${eventId}`);
      this.scheduleNextBroadcast(eventId);
    }

    return { success: true };
  }

  private scheduleNextBroadcast(eventId: string) {
    const timer = setTimeout(() => {
      void this.runBroadcastCycle(eventId);
    }, this.BROADCAST_INTERVAL);
    this.activeHeatmapTimers.set(eventId, timer);
  }

  private async runBroadcastCycle(eventId: string) {
    const heatmapRoom = `heatmap:${eventId}`;
    const room = this.server.sockets.adapter.rooms.get(heatmapRoom);
    if (!room || room.size === 0) {
      this.logger.log(
        `No admins listening; stopping heatmap loop for event: ${eventId}`,
      );
      this.stopBroadcastingForEvent(eventId);
      return;
    }

    try {
      const heatmapData = await this.heatmapService.getHeatmapData(eventId);
      this.server.to(heatmapRoom).emit('heatmap.updated', heatmapData);
    } catch (error) {
      this.logger.error(
        `Failed to broadcast heatmap data for event ${eventId}`,
        error,
      );
    } finally {
      if (this.activeHeatmapTimers.has(eventId)) {
        this.scheduleNextBroadcast(eventId);
      }
    }
  }

  private stopBroadcastingForEvent(eventId: string) {
    const timer = this.activeHeatmapTimers.get(eventId);
    if (timer) {
      clearTimeout(timer);
      this.activeHeatmapTimers.delete(eventId);
    }
  }
}
