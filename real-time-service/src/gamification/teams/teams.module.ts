//src/gamification/teams/teams.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { TeamsService } from './teams.service';
import { TeamsGateway } from './teams.gateway';
import { GamificationModule } from '../gamification.module';
import { SynergyService } from './synergy/synergy.service';
import { TeamNotificationsService } from './notifications/team-notifications.service';
import { TeamChatModule } from './team-chat/team-chat.module';

@Module({
  imports: [forwardRef(() => GamificationModule), TeamChatModule],
  providers: [
    TeamsService,
    TeamsGateway,
    SynergyService,
    TeamNotificationsService,
  ],
  exports: [TeamsService, SynergyService, TeamNotificationsService],
})
export class TeamsModule {}
