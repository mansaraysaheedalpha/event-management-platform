import { Injectable, Logger, Inject, forwardRef } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { SecurityGateway } from './security.gateway';
import { SecurityAlertPayload } from 'src/common/interfaces/security.interface';

@Injectable()
export class SecurityService {
  private readonly logger = new Logger(SecurityService.name);

  constructor(
    @Inject(forwardRef(() => SecurityGateway))
    private readonly securityGateway: SecurityGateway,
  ) {}

  @OnEvent('security-events')
  handleSecurityEvent(payload: SecurityAlertPayload) {
    this.logger.log(`Processing security event: ${payload.type}`);
    // For now, the service's job is simply to trigger the gateway broadcast.
    // In the future, it could also trigger other actions (e.g., locking an account).
    this.securityGateway.broadcastSecurityAlert(payload);
  }
}
