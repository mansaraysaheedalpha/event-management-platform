//src/ops/security/security.service.ts
import { Injectable, Logger, Inject, forwardRef } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { SecurityGateway } from './security.gateway';

import { SecurityEventPayload } from 'src/common/interfaces/security.interface';

/**
 * Service responsible for processing security-related events.
 *
 * Listens to the 'security-events' event stream, then relays alerts
 * to the SecurityGateway for real-time broadcasting to authorized clients.
 *
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
  handleSecurityEvent(payload: SecurityEventPayload) {
    this.logger.log(`Processing security event: ${payload.type}`);

    switch (payload.type) {
      case 'ACCESS_CONTROL_UPDATE':
        this.securityGateway.broadcastAccessControlUpdate(payload);
        break;
      case 'SESSION_CONFLICT_DETECTED':
        this.securityGateway.broadcastSessionConflict(payload);
        break;
      // Default case handles the generic security alerts
      default:
        this.securityGateway.broadcastSecurityAlert(payload);
        break;
    }
  }
}
