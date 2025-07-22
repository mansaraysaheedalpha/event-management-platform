import { Module } from '@nestjs/common';
import { IncidentsModule } from './incidents/incidents.module';

@Module({
  imports: [IncidentsModule],
})
export class AlertsModule {}
