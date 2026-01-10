//src/alerts/incidents/incident.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { ForbiddenException, Inject, Logger, forwardRef } from '@nestjs/common';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { IncidentsService } from './incidents.service';
import { ReportIncidentDto } from './dto/report-incident.dto';
import { IncidentDto } from './dto/incident.dto';
import { UpdateIncidentDto } from './dto/update-incidents.dto';

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class IncidentsGateway {
  private readonly logger = new Logger(IncidentsGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    @Inject(forwardRef(() => IncidentsService))
    private readonly incidentsService: IncidentsService,
  ) {}

  /**
   * Handles the WebSocket event 'incident.report'.
   * Allows an authenticated user to report a new incident for a session.
   * Returns a success message and the ID of the created incident.
   */
  @SubscribeMessage('incident.report')
  async handleReportIncident(
    @MessageBody() dto: ReportIncidentDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const newIncident = await this.incidentsService.reportIncident(
        user.sub,
        sessionId,
        dto,
      );
      return {
        success: true,
        message: 'Your report has been submitted.',
        incidentId: newIncident.id,
      };
    } catch (error) {
      this.logger.error(
        `Failed to report incident for user ${user.sub}`,
        error,
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Handles the WebSocket event 'incidents.join'.
   * Lets an authorized admin join a room to receive real-time incident updates.
   * Checks for required 'ops:incident:read' permission before joining.
   */
  @SubscribeMessage('incidents.join')
  handleJoinIncidentsStream(@ConnectedSocket() client: AuthenticatedSocket) {
    const user = getAuthenticatedUser(client);
    // This permission would be for viewing all incidents in an organization
    const requiredPermission = 'ops:incident:read';

    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to view incidents.',
      );
    }

    const incidentsRoom = `incidents:${user.orgId}`;
    void client.join(incidentsRoom);
    this.logger.log(
      `Admin ${user.sub} joined incidents stream for org ${user.orgId}`,
    );

    return { success: true };
  }

  /**
   * Broadcasts a new incident to all admin clients subscribed to the organization's incident stream.
   * This is triggered internally by the IncidentsService.
   */
  public broadcastNewIncident(incident: IncidentDto) {
    const incidentsRoom = `incidents:${incident.organizationId}`;
    this.server.to(incidentsRoom).emit('incident.new', incident);
    this.logger.log(
      `Broadcasted new incident ${incident.id} to room: ${incidentsRoom}`,
    );
  }

  /**
   * Handles the WebSocket event 'incident.update_status'.
   * Allows an authorized admin to update the status of an incident.
   * Requires 'ops:incident:manage' permission.
   */
  @SubscribeMessage('incident.update_status')
  async handleUpdateIncidentStatus(
    @MessageBody() dto: UpdateIncidentDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const requiredPermission = 'ops:incident:manage';

    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to manage incidents.',
      );
    }

    try {
      const updatedIncident = await this.incidentsService.updateIncidentStatus(
        user.sub,
        user.orgId,
        dto,
      );
      return { success: true, incidentId: updatedIncident.id };
    } catch (error) {
      this.logger.error(
        `Failed to update incident for admin ${user.sub}`,
        error,
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Broadcasts an updated incident to all subscribed admin clients in the organization.
   * Triggered after status change or admin update to the incident.
   */
  public broadcastIncidentUpdate(incident: IncidentDto) {
    const incidentsRoom = `incidents:${incident.organizationId}`;
    this.server.to(incidentsRoom).emit('incident.updated', incident);
    this.logger.log(
      `Broadcasted incident update ${incident.id} to room: ${incidentsRoom}`,
    );
  }
}
