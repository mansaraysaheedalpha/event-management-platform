//src/alerts/notifications/notifications.gateway.ts
import { WebSocketGateway, WebSocketServer } from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Inject, Logger, forwardRef } from '@nestjs/common';
import { NotificationsService } from './notifications.service';
import { SessionReminderDto } from './dto/session-reminder.dto';
import { PersonalNotificationDto } from './dto/personal-notification.dto';
import { EmergencyAlertDto } from './dto/emergency-alerts.dto';
import { ScheduleChangeDto } from './dto/schedule-change.dto';

@WebSocketGateway({
  cors: { origin: true, credentials: true },
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

  public sendPersonalNotification(
    targetUserId: string,
    payload: PersonalNotificationDto,
  ) {
    this.server
      .to(`user:${targetUserId}`)
      .emit('notification.personal', payload);
    this.logger.log(`Sent personal notification to user ${targetUserId}`);
  }

  public broadcastEmergencyAlert(eventId: string, payload: EmergencyAlertDto) {
    this.server.to(`event:${eventId}`).emit('notification.emergency', payload);
    this.logger.log(`Broadcasted emergency alert to event ${eventId}`);
  }

  public broadcastScheduleChange(eventId: string, payload: ScheduleChangeDto) {
    this.server
      .to(`event:${eventId}`)
      .emit('notification.schedule_change', payload);
    this.logger.log(`Broadcasted schedule change to event ${eventId}`);
  }
}
