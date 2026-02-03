// src/live/engagement-conductor/engagement-conductor.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { EngagementConductorGateway } from './engagement-conductor.gateway';
import { AgentInterventionListener } from './agent-intervention.listener';
import { EngagementStreamListener } from './engagement-stream.listener';
import { CommModule } from '../../comm/comm.module';

@Module({
  imports: [
    forwardRef(() => CommModule), // For PollsService and ChatService
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
