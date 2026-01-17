// src/networking/breakout/breakout.module.ts
import { Module } from '@nestjs/common';
import { BreakoutGateway } from './breakout.gateway';
import { BreakoutService } from './breakout.service';

@Module({
  providers: [
    BreakoutGateway,
    BreakoutService,
  ],
  exports: [BreakoutService],
})
export class BreakoutModule {}
