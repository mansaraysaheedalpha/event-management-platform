import { Module } from '@nestjs/common';
import { QnaService } from './qna.service';
import { QnaGateway } from './qna.gateway';
import { GamificationModule } from 'src/gamification/gamification.module';

@Module({
  imports: [GamificationModule],
  providers: [QnaService, QnaGateway],
})
export class QnaModule {}
