// src/expo/expo.module.ts
import { Module } from '@nestjs/common';
import { ExpoGateway } from './expo.gateway';
import { ExpoService } from './expo.service';
import { ExpoAnalyticsService } from './expo-analytics.service';
import { BreakoutModule } from 'src/networking/breakout/breakout.module';

@Module({
  imports: [BreakoutModule], // For DailyService
  providers: [ExpoGateway, ExpoService, ExpoAnalyticsService],
  exports: [ExpoService, ExpoAnalyticsService],
})
export class ExpoModule {}
