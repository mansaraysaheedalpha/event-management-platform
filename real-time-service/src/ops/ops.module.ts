import { Module } from '@nestjs/common';
import { AuditModule } from './audit/audit.module';
import { SecurityModule } from './security/security.module';
import { HealthModule } from './health/health.module';
import { BackchannelModule } from './backchannel/backchannel.module';
import { HeatmapModule } from './heatmap/heatmap.module';

@Module({
  imports: [
    AuditModule,
    SecurityModule,
    HealthModule,
    BackchannelModule,
    HeatmapModule,
  ],
})
export class OpsModule {}
