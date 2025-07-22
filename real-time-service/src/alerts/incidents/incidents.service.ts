import {
  ConflictException,
  ForbiddenException,
  Inject,
  Injectable,
  Logger,
  NotFoundException,
  forwardRef,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import {
  IdempotencyService,
  REDIS_CLIENT,
} from 'src/shared/services/idempotency.service';
import { ReportIncidentDto } from './dto/report-incident.dto';
import { IncidentsGateway } from './incident.gateway';
import { IncidentDto } from './dto/incident.dto';
import { UpdateIncidentDto } from './dto/update-incidents.dto';
import { AuditLogPayload } from 'src/common/interfaces/audit.interface';
import Redis from 'ioredis';
import { SessionMetadata } from 'src/common/interfaces/session.interface';
import { isSessionMetadata } from 'src/common/utils/session.utils';

@Injectable()
export class IncidentsService {
  private readonly logger = new Logger(IncidentsService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
    @Inject(forwardRef(() => IncidentsGateway))
    @Inject(REDIS_CLIENT)
    private readonly redis: Redis,
    @Inject(forwardRef(() => IncidentsGateway))
    private readonly incidentsGateway: IncidentsGateway,
  ) {}

  async reportIncident(
    reporterId: string,
    sessionId: string,
    dto: ReportIncidentDto,
  ): Promise<IncidentDto> {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException(
        'This incident report has already been submitted.',
      );
    }

    // FIX: Fetch real eventId and orgId using our established cache pattern.
    const metadata = await this._getSessionMetadata(sessionId);

    const newIncident = await this.prisma.incident.create({
      data: {
        ...dto,
        reporterId,
        sessionId,
        eventId: metadata.eventId,
        organizationId: metadata.organizationId,
      },
      include: {
        reporter: {
          select: { id: true, firstName: true, lastName: true },
        },
      },
    });

    this.logger.log(
      `New incident ${newIncident.id} reported by user ${reporterId}`,
    );

    // Trigger the gateway to broadcast the new incident to admins
    this.incidentsGateway.broadcastNewIncident(newIncident);

    return newIncident;
  }

  /**
   * Updates the status of an existing incident.
   */
  async updateIncidentStatus(
    adminId: string,
    adminOrgId: string,
    dto: UpdateIncidentDto,
  ) {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException(
        'This incident update has already been processed.',
      );
    }

    // First, find the incident to ensure it exists and belongs to the admin's org
    const incident = await this.prisma.incident.findUnique({
      where: { id: dto.incidentId },
    });

    if (!incident) {
      throw new NotFoundException(
        `Incident with ID ${dto.incidentId} not found.`,
      );
    }

    // Critical Security Check: Ensure the admin belongs to the same org as the incident
    if (incident.organizationId !== adminOrgId) {
      throw new ForbiddenException(
        'You do not have permission to manage this incident.',
      );
    }

    const updatedIncident = await this.prisma.incident.update({
      where: { id: dto.incidentId },
      data: {
        status: dto.status,
        resolutionNotes: dto.resolutionNotes,
        assigneeId: adminId, // Assign the incident to the admin who took action
      },
      include: {
        reporter: { select: { id: true, firstName: true, lastName: true } },
        assignee: { select: { id: true, firstName: true, lastName: true } },
      },
    });

    this.logger.log(
      `Incident ${updatedIncident.id} status updated to ${updatedIncident.status} by admin ${adminId}`,
    );

    // Publish an audit event for this important action
    const auditPayload: AuditLogPayload = {
      action: 'INCIDENT_STATUS_UPDATED',
      actingUserId: adminId,
      organizationId: adminOrgId,
      sessionId: incident.sessionId,
      details: {
        incidentId: incident.id,
        newStatus: dto.status,
      },
    };
    void this._publishAuditEvent(auditPayload);

    // Trigger the gateway to broadcast the update
    this.incidentsGateway.broadcastIncidentUpdate(updatedIncident);

    return updatedIncident;
  }

  // --- THIS IS THE FINAL, WORLD-CLASS IMPLEMENTATION ---
  private async _getSessionMetadata(
    sessionId: string,
  ): Promise<SessionMetadata> {
    const redisKey = `session:info:${sessionId}`;
    const cachedData = await this.redis.get(redisKey);

    if (cachedData) {
      try {
        const parsedData: unknown = JSON.parse(cachedData);
        // Use the type guard to validate and return
        if (isSessionMetadata(parsedData)) {
          return parsedData;
        }
      } catch (error) {
        this.logger.warn(
          `Invalid session metadata in cache for ${sessionId}`,
          error,
        );
      }
    }

    // --- FALLBACK: If cache miss or invalid, fetch from PostgreSQL ---
    this.logger.warn(
      `Session metadata for ${sessionId} not found in cache. Fetching from DB.`,
    );
    const session = await this.prisma.chatSession.findUnique({
      where: { id: sessionId },
      select: { eventId: true, organizationId: true },
    });

    if (!session) {
      throw new NotFoundException(
        `Session with ID ${sessionId} not found in primary database.`,
      );
    }

    // Re-populate the cache for the next request
    await this.redis.set(redisKey, JSON.stringify(session), 'EX', 3600); // Cache for 1 hour

    return session;
  }

  private async _publishAuditEvent(payload: AuditLogPayload) {
    try {
      await this.redis.publish('audit-events', JSON.stringify(payload));
    } catch (error) {
      this.logger.error('Failed to publish audit event', error);
    }
  }
}
