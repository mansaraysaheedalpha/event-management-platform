//src/comm/polls/polls.module.ts
import { Module } from '@nestjs/common';
import { PollsService } from './polls.service';
import { GamificationModule } from 'src/gamification/gamification.module';

@Module({
  imports: [GamificationModule],
  providers: [PollsService],
  exports: [PollsService],
})
export class PollsModule {}
