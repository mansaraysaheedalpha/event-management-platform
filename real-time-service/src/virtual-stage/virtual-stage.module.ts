// src/virtual-stage/virtual-stage.module.ts
import { Module } from '@nestjs/common';
import { VirtualStageController } from './virtual-stage.controller';
import { VirtualStageService } from './virtual-stage.service';
import { BreakoutModule } from '../networking/breakout/breakout.module';

@Module({
  imports: [BreakoutModule], // Reuses DailyService (already exported)
  controllers: [VirtualStageController],
  providers: [VirtualStageService],
})
export class VirtualStageModule {}
