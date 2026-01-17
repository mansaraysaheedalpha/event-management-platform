//src/monetization/sponsors/sponsors.module.ts
import { Module } from '@nestjs/common';
import { SponsorsService } from './sponsors.service';
import { SponsorsGateway } from './sponsors.gateway';
import { SponsorsController } from './sponsors.controller';

@Module({
  controllers: [SponsorsController],
  providers: [SponsorsService, SponsorsGateway],
  exports: [SponsorsGateway],
})
export class SponsorsModule {}
