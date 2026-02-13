// src/gamification/teams/challenges/challenges.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { ChallengesService } from './challenges.service';
import { ChallengesGateway } from './challenges.gateway';
import { ChallengesScheduler } from './challenges.scheduler';
import { GamificationModule } from '../../gamification.module';
import { TeamsModule } from '../teams.module';

@Module({
  imports: [
    forwardRef(() => GamificationModule),
    forwardRef(() => TeamsModule),
  ],
  providers: [ChallengesService, ChallengesGateway, ChallengesScheduler],
  exports: [ChallengesService],
})
export class ChallengesModule {}
