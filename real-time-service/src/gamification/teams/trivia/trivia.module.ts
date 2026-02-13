// src/gamification/teams/trivia/trivia.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { TriviaService } from './trivia.service';
import { TriviaGateway } from './trivia.gateway';
import { GamificationModule } from '../../gamification.module';
import { TeamsModule } from '../teams.module';

@Module({
  imports: [
    forwardRef(() => GamificationModule),
    forwardRef(() => TeamsModule),
  ],
  providers: [TriviaService, TriviaGateway],
  exports: [TriviaService],
})
export class TriviaModule {}
