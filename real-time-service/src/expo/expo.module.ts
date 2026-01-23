// src/expo/expo.module.ts
import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ExpoGateway } from './expo.gateway';
import { ExpoService } from './expo.service';
import { ExpoAnalyticsService } from './expo-analytics.service';
import { ExpoInternalController } from './expo-internal.controller';
import { ExpoController } from './expo.controller';
import { BreakoutModule } from 'src/networking/breakout/breakout.module';

@Module({
  imports: [BreakoutModule, HttpModule], // For DailyService and HTTP calls
  controllers: [ExpoInternalController, ExpoController],
  providers: [ExpoGateway, ExpoService, ExpoAnalyticsService],
  exports: [ExpoService, ExpoAnalyticsService],
})
export class ExpoModule {}
