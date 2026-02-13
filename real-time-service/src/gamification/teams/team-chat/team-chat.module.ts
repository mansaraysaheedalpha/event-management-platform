// src/gamification/teams/team-chat/team-chat.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { TeamChatService } from './team-chat.service';
import { TeamChatGateway } from './team-chat.gateway';
import { GamificationModule } from '../../gamification.module';

@Module({
  imports: [forwardRef(() => GamificationModule)],
  providers: [TeamChatService, TeamChatGateway],
  exports: [TeamChatService],
})
export class TeamChatModule {}
