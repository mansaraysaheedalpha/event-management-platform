//src/gamification/teams/teams.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { TeamsService } from './teams.service';
import { TeamsGateway } from './teams.gateway';
import { GamificationModule } from '../gamification.module';

@Module({
  imports: [forwardRef(() => GamificationModule)],
  providers: [TeamsService, TeamsGateway],
  exports: [TeamsService],
})
export class TeamsModule {}
