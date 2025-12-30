
import {
  ConnectedSocket,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger } from '@nestjs/common';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { getErrorMessage } from 'src/common/utils/error.utils';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class TicketsGateway {
  private readonly logger = new Logger(TicketsGateway.name);
  @WebSocketServer() server: Server;

  @SubscribeMessage('ticket.metrics.join')
  async handleJoinTicketMetrics(
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { eventId } = client.handshake.query as { eventId: string };

    if (!eventId) {
      return { success: false, error: 'Event ID is required' };
    }

    const room = `event:${eventId}:ticket-metrics`;
    client.join(room);

    this.logger.log(`User ${user.sub} joined ticket metrics for event ${eventId}`);

    // Here you would typically fetch the initial data and send it to the client
    // For now, we'll just send a success message

    return { success: true };
  }

  public broadcastTicketMetricsUpdate(eventId: string, data: any) {
    const room = `event:${eventId}:ticket-metrics`;
    this.server.to(room).emit('ticket.metrics.update', data);
    this.logger.log(`Broadcasted ticket metrics update to room ${room}`);
  }
}