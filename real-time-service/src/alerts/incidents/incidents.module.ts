import { Module } from '@nestjs/common';
import { IncidentsService } from './incidents.service';
import { IncidentsGateway } from './incident.gateway';

@Module({
  providers: [IncidentsService, IncidentsGateway],
  exports: [IncidentsService],
})
export class IncidentsModule {}
