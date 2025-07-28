import { Injectable, Logger, Inject, forwardRef } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { SecurityGateway } from './security.gateway';
import { SecurityAlertPayload } from 'src/common/interfaces/security.interface';

/**
 * Service responsible for processing security-related events.
 * 
 * Listens to the 'security-events' event stream, then relays alerts
 * to the SecurityGateway for real-time broadcasting to authorized clients.
 *
 * @example
 * // Somewhere in the system, emit a security event:
 * eventEmitter.emit('security-events', {
 *   type: 'FAILED_LOGIN',
 *   organizationId: 'org123',
 *   details: { userId: 'user456', ip: '1.2.3.4' },
 * });
 */
@Injectable()
export class SecurityService {
  private readonly logger = new Logger(SecurityService.name);

  constructor(
    @Inject(forwardRef(() => SecurityGateway))
    private readonly securityGateway: SecurityGateway,
  ) {}

  /**
   * Handles incoming security events.
   * Currently, it forwards the alert to the gateway for broadcasting.
   * 
   * @param payload - The security alert data (type, organizationId, details).
   */
  @OnEvent('security-events')
  handleSecurityEvent(payload: SecurityAlertPayload) {
    this.logger.log(`Processing security event: ${payload.type}`);

    // Broadcast the security alert to connected clients via the gateway.
    this.securityGateway.broadcastSecurityAlert(payload);

    // Future enhancements could include:
    // - Triggering automatic account lockouts.
    // - Notifying other systems or admins.
    // - Logging to external security services.
  }
}
