import { WebSocketGateway, WebSocketServer } from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Inject, Logger, forwardRef } from '@nestjs/common';
import { SyncService } from './sync.service';

/**
 * The `SyncGateway` is a WebSocket gateway responsible for sending
 * real-time sync updates to individual users when data changes.
 *
 * It pushes updates to specific user rooms using the `sync.update` event.
 * This aligns with the AsyncAPI spec for real-time events.
 *
 * @example
 * // Somewhere in the app:
 * syncGateway.sendSyncUpdate('user123', { type: 'EVENT_UPDATED', data: { ... } });
 *
 * // On the client-side (socket.io):
 * socket.on('sync.update', (payload) => handleUpdate(payload));
 */
@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class SyncGateway {
  private readonly logger = new Logger(SyncGateway.name);

  @WebSocketServer() server: Server;

  constructor(
    @Inject(forwardRef(() => SyncService))
    private readonly syncService: SyncService,
  ) {}

  /**
   * Sends a real-time update to a specific user's WebSocket room.
   *
   * @param targetUserId - The ID of the user to receive the sync update
   * @param payload - The data payload to emit with the `sync.update` event
   * @returns void
   */
  public sendSyncUpdate(targetUserId: string, payload: any): void {
    const userRoom = `user:${targetUserId}`;
    const eventName = 'sync.update';

    this.server.to(userRoom).emit(eventName, payload);
    this.logger.log(`Sent sync update to user ${targetUserId}`);
  }
}
