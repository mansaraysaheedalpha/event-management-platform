import { Module } from '@nestjs/common';
import { IncidentsModule } from './incidents/incidents.module';
import { NotificationsModule } from './notifications/notification.module';
import { AgentNotificationsModule } from './agent-notifications/agent-notifications.module';

@Module({
  imports: [IncidentsModule, NotificationsModule, AgentNotificationsModule],
})
export class AlertsModule {}
