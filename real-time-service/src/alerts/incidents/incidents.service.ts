//src/alerts/incidents/incident.service.ts
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
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
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
    @Inject(REDIS_CLIENT)
    private readonly redis: Redis,
    @Inject(forwardRef(() => IncidentsGateway))
    private readonly incidentsGateway: IncidentsGateway,
  ) {}

  /**
   * Reports a new incident for a session by a user.
   * Uses idempotency to avoid duplicate submissions.
   * Broadcasts the new incident to admins via the gateway.
   *
   * Note: Authorization is handled at the session-join level (ContentGateway validates
   * event registration before allowing users to join). Any authenticated user who has
   * joined a session can report incidents in that session.
   *
   * @param reporterId - ID of the user reporting the incident
   * @param sessionId - ID of the session where the incident occurred
   * @param dto - Payload containing incident details and idempotencyKey
   * @returns The newly created incident with basic reporter info
   * @throws ConflictException - If the same incident has already been submitted
   * @throws NotFoundException - If the session doesn't exist
   */
  async reportIncident(
    reporterId: string,
    sessionId: string,
    dto: ReportIncidentDto,
  ): Promise<IncidentDto> {
    // Fetch session metadata to get eventId and organizationId for the incident record
    const metadata = await this._getSessionMetadata(sessionId);

    // Check idempotency to avoid duplicate submissions
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException(
        'This incident report has already been submitted.',
      );
    }

    // Explicitly specify fields to avoid mass assignment vulnerability
    const newIncident = await this.prisma.incident.create({
      data: {
        type: dto.type,
        severity: dto.severity,
        details: dto.details,
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

    // Publish an audit event for the new incident report
    const auditPayload: AuditLogPayload = {
      action: 'INCIDENT_REPORTED',
      actingUserId: reporterId,
      organizationId: metadata.organizationId,
      sessionId: sessionId,
      details: {
        incidentId: newIncident.id,
        type: newIncident.type,
        severity: newIncident.severity,
      },
    };
    void this._publishAuditEvent(auditPayload);

    // Trigger the gateway to broadcast the new incident to admins
    this.incidentsGateway.broadcastNewIncident(newIncident);

    return newIncident;
  }

  /**
   * Updates the status and resolution of an existing incident.
   * Enforces idempotency and org-based permission validation.
   * Triggers audit logging and real-time broadcasting of the update.
   *
   * @param adminId - ID of the admin performing the update
   * @param adminOrgId - Organization ID of the admin (used for authorization)
   * @param dto - Payload with incident ID, new status, resolution, and idempotencyKey
   * @returns The updated incident with reporter and assignee info
   * @throws ConflictException - If this update has already been processed
   * @throws NotFoundException - If the incident doesn't exist
   * @throws ForbiddenException - If the admin is not allowed to update this incident
   */
  async updateIncidentStatus(
    adminId: string,
    adminOrgId: string,
    dto: UpdateIncidentDto,
  ) {
    // First, find the incident to ensure it exists and belongs to the admin's org
    // Do authorization BEFORE idempotency to avoid consuming keys on unauthorized requests
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

    // Check idempotency AFTER authorization to avoid consuming keys for unauthorized requests
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException(
        'This incident update has already been processed.',
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

  /**
   * Fetches all incidents for an organization.
   * Used when an admin joins the incidents stream to get existing incidents.
   *
   * @param organizationId - ID of the organization
   * @returns Array of incidents with reporter info
   */
  async getIncidentsForOrganization(organizationId: string): Promise<IncidentDto[]> {
    const incidents = await this.prisma.incident.findMany({
      where: { organizationId },
      include: {
        reporter: {
          select: { id: true, firstName: true, lastName: true },
        },
        assignee: {
          select: { id: true, firstName: true, lastName: true },
        },
      },
      orderBy: { createdAt: 'desc' },
    });

    return incidents;
  }

  /**
   * Fetches session metadata (eventId, organizationId) from Redis cache or DB fallback.
   * Ensures structure is valid using a type guard and re-caches if pulled from DB.
   *
   * @param sessionId - ID of the session to get metadata for
   * @returns Session metadata containing eventId and organizationId
   * @throws NotFoundException - If session is not found in DB
   */
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

  /**
   * Publishes an audit event to the Redis channel for system-wide logging.
   * Implements exponential backoff retry logic for resilience.
   *
   * @param payload - Structured data for the audit event
   * @param retries - Number of retry attempts (default: 3)
   * @param baseDelayMs - Base delay between retries in milliseconds (default: 100)
   */
  private async _publishAuditEvent(
    payload: AuditLogPayload,
    retries = 3,
    baseDelayMs = 100,
  ): Promise<void> {
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        await this.redis.publish('audit-events', JSON.stringify(payload));
        return; // Success - exit early
      } catch (error) {
        const isLastAttempt = attempt === retries;

        if (isLastAttempt) {
          // Log failure after all retries exhausted
          this.logger.error(
            `Failed to publish audit event after ${retries + 1} attempts`,
            {
              action: payload.action,
              userId: payload.actingUserId,
              error: error instanceof Error ? error.message : String(error),
            },
          );
          return; // Don't throw - audit failures shouldn't break the main flow
        }

        // Calculate delay with exponential backoff: 100ms, 200ms, 400ms...
        const delayMs = baseDelayMs * Math.pow(2, attempt);
        this.logger.warn(
          `Audit event publish failed (attempt ${attempt + 1}/${retries + 1}), retrying in ${delayMs}ms`,
        );

        // Wait before retrying
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
    }
  }
}
