import { Module } from '@nestjs/common';
import { QnaService } from './qna.service';
import { QnaGateway } from './qna.gateway';

@Module({
  providers: [QnaService, QnaGateway],
})
export class QnaModule {}
