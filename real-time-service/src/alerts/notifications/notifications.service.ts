//src/alerts/notifications/notifications.service.ts
import { Inject, Injectable, Logger, forwardRef } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { NotificationsGateway } from './notifications.gateway';
import { SessionReminderDto } from './dto/session-reminder.dto';
import { PersonalNotificationDto } from './dto/personal-notification.dto';
import { EmergencyAlertDto } from './dto/emergency-alerts.dto';
import { ScheduleChangeDto } from './dto/schedule-change.dto';

type NotificationPayload =
  | PersonalNotificationDto
  | EmergencyAlertDto
  | ScheduleChangeDto
  | SessionReminderDto;

@Injectable()
export class NotificationsService {
  private readonly logger = new Logger(NotificationsService.name);

  constructor(
    @Inject(forwardRef(() => NotificationsGateway))
    private readonly notificationsGateway: NotificationsGateway,
  ) {}

  @OnEvent('notification-events')
  handleNotificationEvent(payload: NotificationPayload) {
    this.logger.log(`Processing notification event: ${payload.type}`);

    // Route the event to the correct gateway method based on its type
    switch (payload.type) {
      case 'SESSION_REMINDER':
        this.notificationsGateway.sendSessionReminder(
          payload.targetUserId,
          payload,
        );
        break;
      case 'PERSONAL_NOTIFICATION':
        this.notificationsGateway.sendPersonalNotification(
          payload.targetUserId,
          payload,
        );
        break;
      case 'EMERGENCY_ALERT':
        this.notificationsGateway.broadcastEmergencyAlert(
          payload.eventId,
          payload,
        );
        break;
      case 'SCHEDULE_CHANGE':
        this.notificationsGateway.broadcastScheduleChange(
          payload.eventId,
          payload,
        );
        break;
    }
  }
}
