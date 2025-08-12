//src/comm/qna/qna.module.ts
import { Module } from '@nestjs/common';
import { QnaService } from './qna.service';
import { GamificationModule } from 'src/gamification/gamification.module';
import { QnaGateway } from './qna.gateway';

@Module({
  imports: [GamificationModule],
  providers: [QnaService, QnaGateway],
})
export class QnaModule {}
