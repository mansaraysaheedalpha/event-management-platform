//src/ops/audit/audit.module.ts
import { Module } from '@nestjs/common';
import { AuditService } from './audit.service';
import { AuditGateway } from './audit.gateway';

@Module({
  providers: [AuditService, AuditGateway],
})
export class AuditModule {}
