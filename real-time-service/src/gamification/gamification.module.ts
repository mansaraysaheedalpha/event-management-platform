//src/gamification/gamification.module.ts
import { Module } from '@nestjs/common';
import { GamificationService } from './gamification.service';
import { TeamsModule } from './teams/teams.module';
import { GamificationGateway } from './gamification.gateway';

@Module({
  imports: [TeamsModule],
  providers: [GamificationService, GamificationGateway],
  exports: [GamificationService],
})
export class GamificationModule {}
