//src/ops/audit/audit.gateway.ts
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
import { AuditService } from './audit.service';
import { AuditLogDto } from './dto/audit-log.dto';

/**
 * AuditGateway manages real-time audit event delivery using WebSockets.
 *
 * Clients connect via the `/events` namespace and subscribe to receive audit logs.
 *
 * @example
 * // Frontend joins the audit stream (must have 'ops:audit:read' permission)
 * socket.emit('ops.audit.join');
 *
 * // Server sends real-time audit logs:
 * socket.on('ops.audit.new', (log) => {
 *   console.log('New audit log:', log);
 * });
 */
@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class AuditGateway {
  private readonly logger = new Logger(AuditGateway.name);

  @WebSocketServer()
  server: Server;

  constructor(
    @Inject(forwardRef(() => AuditService))
    private readonly auditService: AuditService,
  ) {}

  /**
   * Allows an authorized admin client to join a WebSocket room for audit logs.
   * The client will begin receiving real-time audit logs after joining.
   *
   * @param client - The connected WebSocket client with authentication context
   * @returns {{ success: boolean; error?: string }} - Operation status
   *
   * @throws {ForbiddenException} - If the user lacks 'ops:audit:read' permission
   */
  @SubscribeMessage('ops.audit.join')
  handleJoinAuditStream(@ConnectedSocket() client: AuthenticatedSocket): {
    success: boolean;
    error?: string;
  } {
    const user = getAuthenticatedUser(client);
    const requiredPermission = 'ops:audit:read';

    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to view the audit trail.',
      );
    }

    const auditRoom = `audit:${user.orgId}`;
    void client.join(auditRoom);

    this.logger.log(
      `Admin ${user.sub} joined audit stream for org ${user.orgId}`,
    );

    return { success: true };
  }

  /**
   * Broadcasts a new audit log entry to all connected clients in the organization.
   * This method is called internally by the AuditService after saving the log.
   *
   * @param logEntry - The newly created audit log entry
   * @returns {void}
   */
  public broadcastNewLog(logEntry: AuditLogDto): void {
    const auditRoom = `audit:${logEntry.organizationId}`;
    this.server.to(auditRoom).emit('ops.audit.new', logEntry);

    this.logger.log(`Broadcasted new audit log to room: ${auditRoom}`);
  }
}
