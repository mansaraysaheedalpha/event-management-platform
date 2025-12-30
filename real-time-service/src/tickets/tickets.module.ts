
import { Module } from '@nestjs/common';
import { TicketsGateway } from './tickets.gateway';

@Module({
  providers: [TicketsGateway],
})
export class TicketsModule {}