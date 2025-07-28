import { Module } from '@nestjs/common';
import { PollsService } from './polls.service';
import { PollsGateway } from './polls.gateway';
import { GamificationModule } from 'src/gamification/gamification.module';

@Module({
  imports: [GamificationModule],
  providers: [PollsService, PollsGateway],
  exports: [PollsService],
})
export class PollsModule {}
