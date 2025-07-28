import { Module } from '@nestjs/common';
import { ProximityService } from './proximity.service';
import { ProximityGateway } from './proximity.gateway';

@Module({
  providers: [ProximityService, ProximityGateway],
})
export class ProximityModule {}
