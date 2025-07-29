import { Module } from '@nestjs/common';
import { QnaService } from './qna.service';
import { GamificationModule } from 'src/gamification/gamification.module';

@Module({
  imports: [GamificationModule],
  providers: [QnaService],
})
export class QnaModule {}
