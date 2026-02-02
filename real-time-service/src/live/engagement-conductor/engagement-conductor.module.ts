// src/live/engagement-conductor/engagement-conductor.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { EngagementConductorGateway } from './engagement-conductor.gateway';
import { AgentInterventionListener } from './agent-intervention.listener';
import { CommModule } from '../../comm/comm.module';

@Module({
  imports: [
    forwardRef(() => CommModule), // For PollsService and ChatService
  ],
  providers: [EngagementConductorGateway, AgentInterventionListener],
  exports: [EngagementConductorGateway, AgentInterventionListener],
})
export class EngagementConductorModule {}
