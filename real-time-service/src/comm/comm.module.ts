//src/comm/comm.module.ts
import { Module } from '@nestjs/common';
import { QnaModule } from './qna/qna.module';
import { DmModule } from './dm/dm.module';
import { PollsModule } from './polls/polls.module';
import { ChatModule } from './chat/chat.module';

@Module({
  imports: [QnaModule, DmModule, PollsModule, ChatModule],
  exports: [PollsModule, ChatModule], // Re-export for AgentInterventionListener
  providers: [],
})
export class CommModule {}
