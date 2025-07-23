import { WebSocketGateway, WebSocketServer } from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger } from '@nestjs/common';
import { AgendaUpdatePayload } from './agenda.service';

/**
 * WebSocket gateway for broadcasting agenda updates to connected clients.
 *
 * - Namespace: `/events`
 * - Room naming convention: `event:{eventId}`
 * - Events emitted: `agenda.update`
 */
@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class AgendaGateway {
  private readonly logger = new Logger(AgendaGateway.name);
  @WebSocketServer() server: Server;

  /**
   * Emits an agenda update event to all clients in the specific event room.
   *
   * @param payload - Contains the eventId, update type, and full session data.
   */
  broadcastAgendaUpdate(payload: AgendaUpdatePayload) {
    const eventRoom = `event:${payload.eventId}`;
    const eventName = 'agenda.update'; // As defined in our AsyncAPI spec (can be more granular)

    this.server.to(eventRoom).emit(eventName, payload);
    this.logger.log(`Broadcasted agenda update to room: ${eventRoom}`);
  }
}
