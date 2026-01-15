//src/ops/heatmap/heatmap.module.ts
import { Module } from '@nestjs/common';
import { HeatmapService } from './heatmap.service';
import { HeatmapGateway } from './heatmap.gateway';

@Module({
  providers: [HeatmapService, HeatmapGateway],
  exports: [HeatmapService],
})
export class HeatmapModule {}
