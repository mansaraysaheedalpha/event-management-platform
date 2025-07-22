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

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class AuditGateway {
  private readonly logger = new Logger(AuditGateway.name);
  @WebSocketServer() server: Server;

  // We inject the service here, but since the service also injects the gateway,
  // we must use forwardRef to handle the circular dependency.
  constructor(
    @Inject(forwardRef(() => AuditService))
    private readonly auditService: AuditService,
  ) {}

  /**
   * An admin client sends this event to start receiving audit trail updates.
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
   * This is a public method called by the AuditService to broadcast a new log.
   */
  public broadcastNewLog(logEntry: AuditLogDto) {
    const auditRoom = `audit:${logEntry.organizationId}`;
    this.server.to(auditRoom).emit('ops.audit.new', logEntry);
    this.logger.log(`Broadcasted new audit log to room: ${auditRoom}`);
  }
}
