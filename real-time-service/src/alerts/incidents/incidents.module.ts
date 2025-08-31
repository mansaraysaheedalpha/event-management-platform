//src/alerts/incidents/incident.module.ts
import { Module } from '@nestjs/common';
import { IncidentsService } from './incidents.service';
import { IncidentsGateway } from './incident.gateway';
import { IncidentsResolver } from './incidents.resolver';
import { PrismaModule } from '../../prisma.module';

@Module({
  imports: [PrismaModule],
  providers: [IncidentsService, IncidentsGateway, IncidentsResolver],
})
export class IncidentsModule {}
