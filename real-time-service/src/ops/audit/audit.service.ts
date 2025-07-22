import { HttpService } from '@nestjs/axios';
import { Inject, Injectable, Logger, forwardRef } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { firstValueFrom } from 'rxjs';
import { AuditLogPayload } from 'src/common/interfaces/audit.interface';
import { AuditGateway } from './audit.gateway';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { AuditLogDto } from './dto/audit-log.dto';

@Injectable()
export class AuditService {
  private readonly logger = new Logger(AuditService.name);

  constructor(
    private readonly httpService: HttpService,
    // We use forwardRef() to break a circular dependency between the Service and Gateway
    @Inject(forwardRef(() => AuditGateway))
    private readonly auditGateway: AuditGateway,
  ) {}

  /**
   * Listens for all audit events emitted from the SubscriberService.
   */
  @OnEvent('audit-events')
  async handleAuditEvent(payload: AuditLogPayload) {
    this.logger.log(`Processing audit event: ${payload.action}`);

    try {
      // 1. Persist the audit log via internal API call
      const newLogEntry = await this.saveLogToPrimaryDb(payload);

      // 2. If successful, trigger the real-time broadcast
      if (newLogEntry) {
        this.auditGateway.broadcastNewLog(newLogEntry);
      }
    } catch (error) {
      this.logger.error('Failed to process and save audit log', error);
    }
  }

  /**
   * Calls the User & Org service to permanently store the audit log record.
   */
  private async saveLogToPrimaryDb(
    payload: AuditLogPayload,
  ): Promise<AuditLogDto | null> {
    try {
      const userOrgServiceUrl =
        process.env.USER_ORG_SERVICE_URL || 'http://localhost:3001';
      const response = await firstValueFrom(
        this.httpService.post<AuditLogDto>(
          `${userOrgServiceUrl}/internal/audit-logs`,
          payload,
          {
            headers: { 'X-Internal-Api-Key': process.env.INTERNAL_API_KEY },
          },
        ),
      );
      return response.data;
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(
        `Failed to save audit log via internal API: ${errorMessage}`,
        payload,
      );
      return null;
    }
  }
}
