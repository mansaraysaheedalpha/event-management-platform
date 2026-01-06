// src/live/engagement-conductor/engagement-conductor.module.ts
import { Module } from '@nestjs/common';
import { EngagementConductorGateway } from './engagement-conductor.gateway';

@Module({
  providers: [EngagementConductorGateway],
  exports: [EngagementConductorGateway],
})
export class EngagementConductorModule {}
