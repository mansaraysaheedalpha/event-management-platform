//src/live/live.module
import { Module } from '@nestjs/common';
import { AgendaModule } from './agenda/agenda.module';
import { ContentModule } from './content/content.module';
import { DashboardModule } from './dashboard/dashboard.module';
import { ReactionsModule } from './reactions/reactions.module';
import { ValidationModule } from './validation/validation.module'; // <-- Import
import { StreamingModule } from './streaming/streaming.module';
import { EngagementConductorModule } from './engagement-conductor/engagement-conductor.module';

@Module({
  imports: [
    AgendaModule,
    ContentModule,
    DashboardModule,
    ReactionsModule,
    ValidationModule,
    StreamingModule,
    EngagementConductorModule,
  ],
  exports: [DashboardModule],
})
export class LiveModule {}
