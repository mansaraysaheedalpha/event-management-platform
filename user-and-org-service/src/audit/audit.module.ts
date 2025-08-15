//src/audit/audit.module.ts
import { Module } from '@nestjs/common';
import { AuditService } from './audit.service';
import { PrismaModule } from 'src/prisma.module';

@Module({
  imports: [PrismaModule],
  providers: [AuditService],
  exports: [AuditService], // Export it so other services can use it
})
export class AuditModule {}
