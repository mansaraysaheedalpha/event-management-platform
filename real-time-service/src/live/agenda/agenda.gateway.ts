import { WebSocketGateway, WebSocketServer } from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger } from '@nestjs/common';
import { AgendaUpdatePayload } from './agenda.service';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class AgendaGateway {
  private readonly logger = new Logger(AgendaGateway.name);
  @WebSocketServer() server: Server;

  broadcastAgendaUpdate(payload: AgendaUpdatePayload) {
    const eventRoom = `event:${payload.eventId}`;
    const eventName = 'agenda.update'; // As defined in our AsyncAPI spec (can be more granular)

    this.server.to(eventRoom).emit(eventName, payload);
    this.logger.log(`Broadcasted agenda update to room: ${eventRoom}`);
  }
}
