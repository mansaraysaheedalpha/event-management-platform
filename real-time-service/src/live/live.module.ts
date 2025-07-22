import { Module } from '@nestjs/common';
import { AgendaModule } from './agenda/agenda.module';
import { ContentModule } from './content/content.module';
import { DashboardModule } from './dashboard/dashboard.module';
import { ReactionsModule } from './reactions/reactions.module';
import { ValidationModule } from './validation/validation.module'; // <-- Import

@Module({
  imports: [
    ReactionsModule,
    AgendaModule,
    ContentModule,
    DashboardModule,
    ValidationModule, 
  ],
})
export class LiveModule {}
