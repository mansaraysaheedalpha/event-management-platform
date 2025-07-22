import { Module } from '@nestjs/common';
import { AuditModule } from './audit/audit.module';
import { SecurityModule } from './security/security.module';
import { HealthModule } from './health/health.module';

@Module({
  imports: [AuditModule, SecurityModule, HealthModule],
})
export class OpsModule {}
