//src/gamification/teams/teams.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { TeamsService } from './teams.service';
import { TeamsGateway } from './teams.gateway';
import { GamificationModule } from '../gamification.module';
import { SynergyService } from './synergy/synergy.service';
import { TeamNotificationsService } from './notifications/team-notifications.service';
import { TeamChatModule } from './team-chat/team-chat.module';
import { TriviaModule } from './trivia/trivia.module';
import { ChallengesModule } from './challenges/challenges.module';

@Module({
  imports: [
    forwardRef(() => GamificationModule),
    forwardRef(() => ChallengesModule),
    TeamChatModule,
    TriviaModule,
  ],
  providers: [
    TeamsService,
    TeamsGateway,
    SynergyService,
    TeamNotificationsService,
  ],
  exports: [TeamsService, SynergyService, TeamNotificationsService],
})
export class TeamsModule {}
