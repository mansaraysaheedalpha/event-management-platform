//src/ops/health/health.gateway.ts
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
import { HealthService } from './health.service';
import { HealthStatusDto } from './dto/health-status.dto';

/**
 * WebSocket gateway responsible for streaming system health updates
 * to super-admin users. Uses a single global room: `system-health`.
 *
 * @example
 * // Client emits this to start receiving health updates
 * socket.emit('ops.health.join');
 *
 * // Client listens to this for real-time status updates
 * socket.on('ops.system.health', (payload) => { ... });
 */
@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class HealthGateway {
  private static readonly HEALTH_ROOM = 'system-health';
  private readonly logger = new Logger(HealthGateway.name);

  /**
   * WebSocket server instance injected by NestJS.
   */
  @WebSocketServer() server: Server;

  /**
   * Injects the HealthService using forwardRef to resolve circular dependency.
   */
  constructor(
    @Inject(forwardRef(() => HealthService))
    private readonly healthService: HealthService,
  ) {}

  /**
   * Handles a super-admin client subscribing to the global health stream.
   * Joins the client to a `system-health` room to receive status updates.
   *
   * @param client - The connected and authenticated WebSocket client.
   * @returns An object with `{ success: true }` or throws if unauthorized.
   */
  @SubscribeMessage('ops.health.join')
  async handleJoinHealthStream(
    @ConnectedSocket() client: AuthenticatedSocket,
  ): Promise<{ success: boolean }> {
    const user = getAuthenticatedUser(client);
    const requiredPermission = 'system:health:read';

    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to view system health.',
      );
    }

    await client.join(HealthGateway.HEALTH_ROOM);
    this.logger.log(`Super-admin ${user.sub} joined system health stream.`);

    return { success: true };
  }

  /**
   * Public method to broadcast health status updates to all
   * clients in the `system-health` room.
   *
   * @param payload - The health status update to send.
   */
  public broadcastHealthStatus(payload: HealthStatusDto): void {
    this.server
      .to(HealthGateway.HEALTH_ROOM)
      .emit('ops.system.health', payload);
    this.logger.log(
      `Broadcasted system health update: ${payload.service} is ${payload.status}`,
    );
  }
}
