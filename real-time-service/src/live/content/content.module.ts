//src/content/content.module.ts
import { forwardRef, Module } from '@nestjs/common';
import { ContentService } from './content.service';
import { SharedModule } from 'src/shared/shared.module';
import { ContentGateway } from './content.gateway';
import { ChatModule } from 'src/comm/chat/chat.module';
import { QnaModule } from 'src/comm/qna/qna.module';
import { PollsModule } from 'src/comm/polls/polls.module';

@Module({
  imports: [
    SharedModule,
    forwardRef(() => ChatModule),
    forwardRef(() => QnaModule),
    forwardRef(() => PollsModule),
  ],
  providers: [ContentGateway, ContentService],
  exports: [ContentService],
})
export class ContentModule {}
