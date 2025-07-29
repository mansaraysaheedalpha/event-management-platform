import { Module } from '@nestjs/common';
import { SponsorsService } from './sponsors.service';
import { SponsorsGateway } from './sponsors.gateway';

@Module({
  providers: [SponsorsService, SponsorsGateway],
})
export class SponsorsModule {}
