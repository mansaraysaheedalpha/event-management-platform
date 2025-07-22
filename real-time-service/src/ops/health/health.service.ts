import { Injectable, Logger, Inject, forwardRef } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { HealthGateway } from './health.gateway';
import { HealthStatusDto } from './dto/health-status.dto';

@Injectable()
export class HealthService {
  private readonly logger = new Logger(HealthService.name);

  constructor(
    @Inject(forwardRef(() => HealthGateway))
    private readonly healthGateway: HealthGateway,
  ) {}

  @OnEvent('system-health-events')
  handleHealthEvent(payload: HealthStatusDto) {
    this.logger.log(
      `Processing system health event for service: ${payload.service}`,
    );
    this.healthGateway.broadcastHealthStatus(payload);
  }
}
