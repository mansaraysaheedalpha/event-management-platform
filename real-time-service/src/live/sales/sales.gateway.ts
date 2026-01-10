//src/live/sales/sales.gatway.ts
import { WebSocketGateway, WebSocketServer } from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { TicketAvailabilityDto } from './dto/ticket-availability.dto';

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class SalesGateway {
  private readonly logger = new Logger(SalesGateway.name);
  @WebSocketServer() server: Server;

  /**
   * Listens for internal sales events and broadcasts them to the event room.
   */
  @OnEvent('sales-events')
  handleTicketAvailabilityUpdate(payload: TicketAvailabilityDto) {
    const eventRoom = `event:${payload.eventId}`;
    const eventName = 'ticket.availability.updated';

    this.server.to(eventRoom).emit(eventName, payload);
    this.logger.log(`Broadcasted ticket availability to room: ${eventRoom}`);
  }
}
