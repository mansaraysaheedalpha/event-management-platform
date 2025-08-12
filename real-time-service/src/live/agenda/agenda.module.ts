//src/agenda/agenda.module.ts
import { Module } from '@nestjs/common';
import { AgendaService } from './agenda.service';
import { AgendaGateway } from './agenda.gateway';

@Module({
  providers: [AgendaService, AgendaGateway],
  exports: [AgendaService],
})
export class AgendaModule {}
