import { HttpService } from '@nestjs/axios';
import { Inject, Injectable, Logger, forwardRef } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { firstValueFrom } from 'rxjs';
import { AuditLogPayload } from 'src/common/interfaces/audit.interface';
import { AuditGateway } from './audit.gateway';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { AuditLogDto } from './dto/audit-log.dto';

/**
 * AuditService handles audit event processing, including:
 * - Persisting logs via internal HTTP requests
 * - Broadcasting new audit logs to WebSocket clients
 *
 * @example
 * // Emits an audit log and handles real-time notification
 * auditService.handleAuditEvent({
 *   action: 'USER_LOGIN',
 *   userId: 'abc123',
 *   organizationId: 'org456',
 *   timestamp: new Date().toISOString()
 * });
 */
@Injectable()
export class AuditService {
  private readonly logger = new Logger(AuditService.name);

  constructor(
    private readonly httpService: HttpService,

    // forwardRef is used to resolve circular dependency between service and gateway
    @Inject(forwardRef(() => AuditGateway))
    private readonly auditGateway: AuditGateway,
  ) {}

  /**
   * Event listener for 'audit-events' published by other services.
   * Tries to persist the log via HTTP, then broadcasts it over WebSocket if successful.
   *
   * @param payload - The audit data to log and broadcast
   * @returns {Promise<void>}
   */
  @OnEvent('audit-events')
  async handleAuditEvent(payload: AuditLogPayload): Promise<void> {
    this.logger.log(`Processing audit event: ${payload.action}`);

    try {
      const newLogEntry = await this.saveLogToPrimaryDb(payload);

      if (newLogEntry) {
        this.auditGateway.broadcastNewLog(newLogEntry);
      }
    } catch (error) {
      this.logger.error('Failed to process and save audit log', error);
    }
  }

  /**
   * Sends the audit payload to the primary User/Org service via internal API call.
   *
   * @param payload - Audit event details to persist
   * @returns {Promise<AuditLogDto | null>} - The persisted log or null if failed
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
            headers: {
              'X-Internal-Api-Key': process.env.INTERNAL_API_KEY,
            },
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
