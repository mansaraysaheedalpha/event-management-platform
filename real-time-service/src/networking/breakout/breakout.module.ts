// src/networking/breakout/breakout.module.ts
import { Module } from '@nestjs/common';
import { BreakoutGateway } from './breakout.gateway';
import { BreakoutService } from './breakout.service';
import { SegmentService } from './segment.service';
import { DailyService } from './daily.service';

@Module({
  providers: [
    BreakoutGateway,
    BreakoutService,
    SegmentService,
    DailyService,
  ],
  exports: [BreakoutService, SegmentService, DailyService],
})
export class BreakoutModule {}
