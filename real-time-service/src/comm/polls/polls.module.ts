//src/comm/polls/polls.module.ts
import { Module } from '@nestjs/common';
import { PollsService } from './polls.service';
import { PollsGateway } from './polls.gateway';
import { GamificationModule } from 'src/gamification/gamification.module';
import { SharedModule } from 'src/shared/shared.module';

@Module({
  imports: [GamificationModule, SharedModule],
  providers: [PollsService, PollsGateway],
  exports: [PollsService],
})
export class PollsModule {}
