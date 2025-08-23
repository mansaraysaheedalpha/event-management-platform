//src/audit/audit.service.ts
import { Injectable } from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';

interface LogData {
  action: string;
  actingUserId: string;
  organizationId?: string;
  targetUserId?: string;
  details?: Record<string, any>;
}

@Injectable()
export class AuditService {
  constructor(private prisma: PrismaService) {}

  async log(data: LogData) {
    await this.prisma.auditLog.create({
      data: {
        action: data.action,
        actingUserId: data.actingUserId,
        organizationId: data.organizationId,
        targetUserId: data.targetUserId,
        details: data.details || undefined,
      },
    });
  }
}
