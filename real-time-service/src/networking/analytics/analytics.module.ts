//src/networking/analytics/analytics.module.ts
import { Module } from '@nestjs/common';
import { NetworkingAnalyticsService } from './analytics.service';
import { NetworkingAnalyticsController } from './analytics.controller';
import { PrismaService } from 'src/prisma.service';

@Module({
  controllers: [NetworkingAnalyticsController],
  providers: [NetworkingAnalyticsService, PrismaService],
  exports: [NetworkingAnalyticsService],
})
export class NetworkingAnalyticsModule {}
