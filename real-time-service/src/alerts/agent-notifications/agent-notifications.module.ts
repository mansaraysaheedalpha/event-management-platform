import { Module } from '@nestjs/common';
import { AgentNotificationsController } from './agent-notifications.controller';
import { AgentNotificationsService } from './agent-notifications.service';
import { AgentNotificationsGateway } from './agent-notifications.gateway';

@Module({
  controllers: [AgentNotificationsController],
  providers: [AgentNotificationsService, AgentNotificationsGateway],
  exports: [AgentNotificationsService],
})
export class AgentNotificationsModule {}
