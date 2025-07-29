import { WebSocketGateway, WebSocketServer } from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Inject, Logger, forwardRef } from '@nestjs/common';
import { NotificationsService } from './notifications.service';
import { SessionReminderDto } from './dto/session-reminder.dto';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class NotificationsGateway {
  private readonly logger = new Logger(NotificationsGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    @Inject(forwardRef(() => NotificationsService))
    private readonly notificationsService: NotificationsService,
  ) {}

  public sendSessionReminder(
    targetUserId: string,
    payload: SessionReminderDto,
  ) {
    const userRoom = `user:${targetUserId}`;
    const eventName = 'notification.session_reminder';
    this.server.to(userRoom).emit(eventName, payload);
    this.logger.log(`Sent session reminder to user ${targetUserId}`);
  }
}
