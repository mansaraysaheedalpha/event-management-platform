// src/notifications/notifications.module.ts
import { Module } from '@nestjs/common';
import { UpdateNotificationsGateway } from './update-notifications.gateway';
import { SharedModule } from '../shared/shared.module';

@Module({
  imports: [SharedModule],
  providers: [UpdateNotificationsGateway],
  exports: [UpdateNotificationsGateway],
})
export class NotificationsModule {}
