//src/comm/qna/qna.module.ts
import { Module } from '@nestjs/common';
import { QnaService } from './qna.service';
import { GamificationModule } from 'src/gamification/gamification.module';
import { QnaGateway } from './qna.gateway';
import { SharedModule } from 'src/shared/shared.module';

@Module({
  imports: [GamificationModule, SharedModule],
  providers: [QnaService, QnaGateway],
  exports: [QnaService],
})
export class QnaModule {}
