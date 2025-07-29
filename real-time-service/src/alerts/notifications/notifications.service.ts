import { Inject, Injectable, Logger, forwardRef } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { NotificationsGateway } from './notifications.gateway';
import { SessionReminderDto } from './dto/session-reminder.dto';

@Injectable()
export class NotificationsService {
  private readonly logger = new Logger(NotificationsService.name);

  constructor(
    @Inject(forwardRef(() => NotificationsGateway))
    private readonly notificationsGateway: NotificationsGateway,
  ) {}

  @OnEvent('notification-events')
  handleNotificationEvent(payload: SessionReminderDto) {
    if (payload.type === 'SESSION_REMINDER') {
      this.logger.log(
        `Processing session reminder for user: ${payload.targetUserId}`,
      );
      this.notificationsGateway.sendSessionReminder(
        payload.targetUserId,
        payload,
      );
    }
  }
}
