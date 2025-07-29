import { Module } from '@nestjs/common';
import { IncidentsModule } from './incidents/incidents.module';
import { NotificationsModule } from './notifications/notification.module';

@Module({
  imports: [IncidentsModule, NotificationsModule],
})
export class AlertsModule {}
