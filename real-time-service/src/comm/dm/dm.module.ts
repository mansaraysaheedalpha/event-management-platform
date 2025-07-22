import { Module } from '@nestjs/common';
import { DmService } from './dm.service';
import { DmGateway } from './dm.gateway';

@Module({
  providers: [DmService, DmGateway],
  exports: [DmService],
})
export class DmModule {}
