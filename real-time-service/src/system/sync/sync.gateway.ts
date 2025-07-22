import { WebSocketGateway, WebSocketServer } from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Inject, Logger, forwardRef } from '@nestjs/common';
import { SyncService } from './sync.service';

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

  public sendSyncUpdate(targetUserId: string, payload: any) {
    const userRoom = `user:${targetUserId}`;
    // This event name matches the channel in our AsyncAPI spec
    const eventName = 'sync.update';

    this.server.to(userRoom).emit(eventName, payload);
    this.logger.log(`Sent sync update to user ${targetUserId}`);
  }
}
