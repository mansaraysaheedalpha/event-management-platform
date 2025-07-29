import { Module } from '@nestjs/common';
import { AgendaModule } from './agenda/agenda.module';
import { ContentModule } from './content/content.module';
import { DashboardModule } from './dashboard/dashboard.module';
import { ReactionsModule } from './reactions/reactions.module';
import { ValidationModule } from './validation/validation.module'; // <-- Import
import { StreamingModule } from './streaming/streaming.module';

@Module({
  imports: [
    AgendaModule,
    ContentModule,
    DashboardModule,
    ReactionsModule,
    ValidationModule,
    StreamingModule,
  ],
})
export class LiveModule {}
