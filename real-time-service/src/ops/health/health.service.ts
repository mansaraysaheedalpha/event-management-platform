import { Injectable, Logger, Inject, forwardRef } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { HealthGateway } from './health.gateway';
import { HealthStatusDto } from './dto/health-status.dto';

/**
 * Service responsible for handling system health events and
 * broadcasting them via WebSockets to connected super-admins.
 *
 * It listens for `'system-health-events'` and passes the payload
 * to the gateway for broadcasting.
 *
 * @example
 * // Somewhere in the system
 * eventEmitter.emit('system-health-events', {
 *   service: 'auth-service',
 *   status: 'degraded',
 * });
 */
@Injectable()
export class HealthService {
  private readonly logger = new Logger(HealthService.name);

  /**
   * Injects the HealthGateway using forwardRef to avoid circular dependency issues.
   */
  constructor(
    @Inject(forwardRef(() => HealthGateway))
    private readonly healthGateway: HealthGateway,
  ) {}

  /**
   * Event handler for system health changes.
   * When a `system-health-events` event is emitted,
   * this method logs it and forwards it to all subscribed clients.
   *
   * @param payload - The health status info to broadcast.
   */
  @OnEvent('system-health-events')
  handleHealthEvent(payload: HealthStatusDto): void {
    this.logger.log(
      `Processing system health event for service: ${payload.service}`,
    );
    this.healthGateway.broadcastHealthStatus(payload);
  }
}
