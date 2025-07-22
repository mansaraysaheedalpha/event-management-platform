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

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class HealthGateway {
  private readonly logger = new Logger(HealthGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    @Inject(forwardRef(() => HealthService))
    private readonly healthService: HealthService,
  ) {}

  @SubscribeMessage('ops.health.join')
  handleJoinHealthStream(@ConnectedSocket() client: AuthenticatedSocket) {
    const user = getAuthenticatedUser(client);
    // This permission should be reserved for super-admins of your platform
    const requiredPermission = 'system:health:read';

    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to view system health.',
      );
    }

    const healthRoom = `system-health`; // A single, global room for this
    void client.join(healthRoom);
    this.logger.log(`Super-admin ${user.sub} joined system health stream.`);

    return { success: true };
  }

  public broadcastHealthStatus(payload: HealthStatusDto) {
    const healthRoom = `system-health`;
    this.server.to(healthRoom).emit('ops.system.health', payload);
    this.logger.log(
      `Broadcasted system health update: ${payload.service} is ${payload.status}`,
    );
  }
}
