import { Module } from '@nestjs/common';
import { AgendaService } from './agenda.service';
import { AgendaGateway } from './agenda.gateway';

@Module({
  providers: [AgendaService, AgendaGateway],
})
export class AgendaModule {}
