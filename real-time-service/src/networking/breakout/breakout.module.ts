// src/networking/breakout/breakout.module.ts
import { Module } from '@nestjs/common';
import { BreakoutGateway } from './breakout.gateway';
import { BreakoutService } from './breakout.service';
import { DailyService } from './daily.service';

@Module({
  providers: [
    BreakoutGateway,
    BreakoutService,
    DailyService,
  ],
  exports: [BreakoutService, DailyService],
})
export class BreakoutModule {}
