import { Injectable, Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { AgendaGateway } from './agenda.gateway';


/**
 * Describes the shape of an agenda update event payload.
 */
export interface AgendaUpdatePayload {
  eventId: string;
  updateType: 'SESSION_UPDATED' | 'SESSION_CANCELED' | 'SESSION_ADDED';
  sessionData: Record<string, unknown>; // A generic object for session data // The full session object from the Event Lifecycle service
}
/**
 * Service that listens to agenda updates and dispatches them through WebSocket.
 *
 * Usage:
 *  - Another microservice emits `agenda-updates`
 *  - This service picks it up, logs, and passes it to `AgendaGateway`
 */
@Injectable()
export class AgendaService {
  private readonly logger = new Logger(AgendaService.name);

  constructor(private readonly agendaGateway: AgendaGateway) {}

  /**
   * Handles internal `agenda-updates` events and broadcasts them using WebSockets.
   *
   * @param payload - The agenda update payload containing session changes.
   */
  @OnEvent('agenda-updates') // This method listens for the 'agenda-updates' event
  handleAgendaUpdate(payload: AgendaUpdatePayload) {
    this.logger.log(`Processing agenda update for event: ${payload.eventId}`);
    this.agendaGateway.broadcastAgendaUpdate(payload);
  }
}
