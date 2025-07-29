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
import { SecurityService } from './security.service';
import { SecurityAlertPayload } from 'src/common/interfaces/security.interface';

/**
 * Gateway for handling real-time security event communication over WebSockets.
 * Only authorized users (typically admins) are allowed to join.
 *
 * @example
 * // Client emits:
 * socket.emit('ops.security.join');
 *
 * // Server pushes:
 * socket.on('ops.security.alert', (payload) => handleAlert(payload));
 */
@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class SecurityGateway {
  private readonly logger = new Logger(SecurityGateway.name);

  @WebSocketServer()
  server: Server;

  constructor(
    @Inject(forwardRef(() => SecurityService))
    private readonly securityService: SecurityService,
  ) {}

  /**
   * Handles a client request to join the security alerts room.
   * Only users with 'ops:security:read' permission can access.
   *
   * @param client - The authenticated socket instance.
   * @returns Object with success status if joined.
   * @throws ForbiddenException if the user lacks permission.
   */
  @SubscribeMessage('ops.security.join')
  handleJoinSecurityStream(@ConnectedSocket() client: AuthenticatedSocket) {
    const user = getAuthenticatedUser(client);
    const requiredPermission = 'ops:security:read';

    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to view security alerts.',
      );
    }

    const securityRoom = `security:${user.orgId}`;
    void client.join(securityRoom);

    this.logger.log(
      `Admin ${user.sub} joined security stream for org ${user.orgId}`,
    );

    return { success: true };
  }

  /**
   * Emits a security alert to all users in the organization's security room.
   *
   * @param payload - The security alert data containing org ID and alert info.
   */
  public broadcastSecurityAlert(payload: SecurityAlertPayload) {
    const securityRoom = `security:${payload.organizationId}`;
    this.server.to(securityRoom).emit('ops.security.alert', payload);
    this.logger.log(`Broadcasted security alert to room: ${securityRoom}`);
  }
}
