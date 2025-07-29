import { Module } from '@nestjs/common';
import { QnaModule } from './qna/qna.module';
import { DmModule } from './dm/dm.module';
import { PollsModule } from './polls/polls.module';
import { ChatModule } from './chat/chat.module';

@Module({
  imports: [QnaModule, DmModule, PollsModule, ChatModule],
  providers: [],
})
export class CommModule {}
