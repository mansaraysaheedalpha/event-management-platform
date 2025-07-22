import { Module } from '@nestjs/common';
import { HealthService } from './health.service';
import { HealthGateway } from './health.gateway';

@Module({
  providers: [HealthService, HealthGateway],
})
export class HealthModule {}
