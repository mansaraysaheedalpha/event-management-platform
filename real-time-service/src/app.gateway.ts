// src/app.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  OnGatewayConnection,
  OnGatewayDisconnect,
  OnGatewayInit,
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

interface MultitenantMetricsDto {
  orgId: string;
  metrics: object;
}

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class AppGateway
  implements
    OnGatewayInit,
    OnGatewayConnection,
    OnGatewayDisconnect,
    OnApplicationShutdown
{
  @WebSocketServer()
  server: Server;

  private readonly logger = new Logger('AppGateway');
  private activeDashboardTimers = new Map<string, NodeJS.Timeout>();
  private readonly BROADCAST_INTERVAL = 5000;
  private isGatewayInitialized = false;

  constructor(
    private readonly connectionService: ConnectionService,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
    @Inject(forwardRef(() => DashboardService))
    private readonly dashboardService: DashboardService,
  ) {}

  afterInit(server: Server) {
    this.server = server;
    server.setMaxListeners(30);
    this.isGatewayInitialized = true;
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

      const userRoom = `user:${payload.sub}`;
      await client.join(userRoom);
      this.logger.log(
        `✅ Client Connected: ${client.id} | User: ${payload.email} | Joined room: ${userRoom}`,
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

  @SubscribeMessage('event.join')
  async handleJoinEvent(
    @ConnectedSocket() client: AuthenticatedSocket,
    @MessageBody() data: { eventId?: string },
  ): Promise<{ success: boolean; error?: string }> {
    const user = getAuthenticatedUser(client);
    // Accept eventId from message body or query params
    const eventId =
      data?.eventId || (client.handshake.query as { eventId?: string }).eventId;

    if (!eventId) {
      this.logger.warn(
        `Event join failed for user ${user.sub}: Missing eventId`,
      );
      return { success: false, error: 'Event ID is required' };
    }

    const eventRoom = `event:${eventId}`;
    await client.join(eventRoom);
    this.logger.log(`✅ User ${user.sub} joined event room: ${eventRoom}`);

    return { success: true };
  }

  @SubscribeMessage('event.leave')
  async handleLeaveEvent(
    @ConnectedSocket() client: AuthenticatedSocket,
    @MessageBody() data: { eventId?: string },
  ): Promise<{ success: boolean }> {
    const user = getAuthenticatedUser(client);
    // Accept eventId from message body or query params
    const eventId =
      data?.eventId || (client.handshake.query as { eventId?: string }).eventId;

    if (eventId) {
      const eventRoom = `event:${eventId}`;
      await client.leave(eventRoom);
      this.logger.log(`User ${user.sub} left event room: ${eventRoom}`);
    }

    return { success: true };
  }

  @SubscribeMessage('dashboard.join')
  async handleJoinDashboard(
    @ConnectedSocket() client: AuthenticatedSocket,
  ): Promise<{
    success: boolean;
    error?: string;
  }> {
    if (!this.isGatewayInitialized || !this.server) {
      const errorMsg = 'Gateway not fully initialized. Please try again.';
      this.logger.error(errorMsg);
      return { success: false, error: errorMsg };
    }

    const user = getAuthenticatedUser(client);
    const { eventId } = client.handshake.query as { eventId: string };
    this.logger.log(
      `🎯 Received dashboard.join from user ${user.sub} for event ${eventId}`,
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
    await client.join(dashboardRoom);
    this.logger.log(`✅ Admin ${user.sub} joined room: ${dashboardRoom}`);

    if (!this.activeDashboardTimers.has(eventId)) {
      this.logger.log(
        `🚀 Starting dashboard broadcast loop for event: ${eventId}`,
      );
      // ✅ CRITICAL FIX: Wait 1 second (1000ms) for Socket.IO to register the client
      this.scheduleNextBroadcast(eventId, 1000);
    } else {
      this.logger.log(
        `⏭️ Broadcast loop already running for event: ${eventId}`,
      );
    }

    return { success: true };
  }

  private scheduleNextBroadcast(
    eventId: string,
    delay: number = this.BROADCAST_INTERVAL,
  ) {
    const timer = setTimeout(() => {
      void this.runBroadcastCycle(eventId);
    }, delay);
    this.activeDashboardTimers.set(eventId, timer);
  }

  private async runBroadcastCycle(eventId: string) {
    if (!this.isGatewayInitialized || !this.server || !this.server.sockets) {
      this.logger.error(
        `Gateway not initialized when trying to broadcast for event: ${eventId}`,
      );
      this.stopBroadcastingForEvent(eventId);
      return;
    }

    const dashboardRoom = `dashboard:${eventId}`;

    try {
      // Use the namespace's adapter (this.server is the /events namespace Server)
      // fetchSockets() is the reliable way to get sockets in a room across namespaces
      const socketsInRoom = await this.server.in(dashboardRoom).fetchSockets();

      if (socketsInRoom.length === 0) {
        this.logger.log(
          `No admins listening; stopping dashboard loop for event: ${eventId}`,
        );
        this.stopBroadcastingForEvent(eventId);
        return;
      }

      this.logger.log(
        `📡 Broadcasting to ${socketsInRoom.length} admin(s) for event: ${eventId}`,
      );

      const dashboardData =
        await this.dashboardService.getDashboardData(eventId);
      this.server.to(dashboardRoom).emit('dashboard.update', dashboardData);
      this.logger.log(`📊 Broadcasted data: ${JSON.stringify(dashboardData)}`);
    } catch (error) {
      this.logger.error(
        `Failed to fetch or broadcast dashboard data for event ${eventId}`,
        error,
      );
    } finally {
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

  @OnEvent('capacity-events')
  handleCapacityUpdate(payload: CapacityUpdateDto) {
    this.logger.log(
      `Processing capacity update for resource: ${payload.resourceId}`,
    );
    this.broadcastCapacityUpdate(payload);
  }

  public broadcastCapacityUpdate(payload: CapacityUpdateDto) {
    if (!this.isGatewayInitialized || !this.server) {
      this.logger.warn('Cannot broadcast: Gateway not initialized');
      return;
    }

    const adminRoom = `dashboard:${payload.eventId}`;
    const eventName = 'dashboard.capacity.updated';
    this.server.to(adminRoom).emit(eventName, payload);
    this.logger.log(`Broadcasted capacity update to room ${adminRoom}`);
  }

  @OnEvent('system-metrics-events')
  async handleSystemMetrics(payload: MultitenantMetricsDto) {
    this.logger.log(`Processing system metrics for org: ${payload.orgId}`);

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

  public broadcastSystemMetrics(
    eventIds: string[],
    payload: MultitenantMetricsDto,
  ) {
    if (!this.isGatewayInitialized || !this.server) {
      this.logger.warn('Cannot broadcast: Gateway not initialized');
      return;
    }

    const eventName = 'dashboard.metrics.updated';

    for (const eventId of eventIds) {
      const adminRoom = `dashboard:${eventId}`;
      this.server.to(adminRoom).emit(eventName, payload);
    }

    this.logger.log(
      `Broadcasted system metrics to ${eventIds.length} dashboards for org ${payload.orgId}`,
    );
  }

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
