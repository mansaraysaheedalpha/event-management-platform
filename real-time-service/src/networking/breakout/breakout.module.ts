// src/networking/breakout/breakout.module.ts
import { Module } from '@nestjs/common';
import { BreakoutGateway } from './breakout.gateway';
import { BreakoutService } from './breakout.service';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';

@Module({
  providers: [
    BreakoutGateway,
    BreakoutService,
    PrismaService,
    IdempotencyService,
  ],
  exports: [BreakoutService],
})
export class BreakoutModule {}
