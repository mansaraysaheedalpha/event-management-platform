//src/live/streaming/streaming.module.ts
import { Module } from '@nestjs/common';
import { StreamingController } from './streaming.controller';
import { StreamingGateway } from './streaming.gateway';

@Module({
  controllers: [StreamingController],
  providers: [StreamingGateway],
})
export class StreamingModule {}
