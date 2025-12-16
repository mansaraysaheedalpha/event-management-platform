//src/comm/chat/chat.module.ts
import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ChatService } from './chat.service';
import { ChatGateway } from './chat.gateway';
import { GamificationModule } from 'src/gamification/gamification.module';
import { SharedModule } from 'src/shared/shared.module';

@Module({
  imports: [GamificationModule, SharedModule, HttpModule],
  providers: [ChatService, ChatGateway],
  exports: [ChatService],
})
export class ChatModule {}
