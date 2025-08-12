//src/comm/comm.module.ts
import { Module } from '@nestjs/common';
import { QnaModule } from './qna/qna.module';
import { DmModule } from './dm/dm.module';
import { PollsModule } from './polls/polls.module';
import { ChatModule } from './chat/chat.module';
import { SessionModule } from './session/session.module';

@Module({
  imports: [QnaModule, DmModule, PollsModule, ChatModule, SessionModule],
  providers: [],
})
export class CommModule {}
