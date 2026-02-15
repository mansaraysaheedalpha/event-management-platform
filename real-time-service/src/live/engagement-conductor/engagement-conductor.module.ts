// src/live/engagement-conductor/engagement-conductor.module.ts
import { Module } from '@nestjs/common';
import { EngagementConductorGateway } from './engagement-conductor.gateway';
import { AgentInterventionListener } from './agent-intervention.listener';
import { EngagementStreamListener } from './engagement-stream.listener';
import { CommModule } from '../../comm/comm.module';

@Module({
  imports: [
    CommModule, // MED-12 FIX: One-way dependency, no forwardRef needed
  ],
  providers: [
    EngagementConductorGateway,
    AgentInterventionListener,
    EngagementStreamListener,
  ],
  exports: [
    EngagementConductorGateway,
    AgentInterventionListener,
    EngagementStreamListener,
  ],
})
export class EngagementConductorModule {}
