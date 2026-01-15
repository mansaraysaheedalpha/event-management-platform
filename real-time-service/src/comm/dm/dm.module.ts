//src/comm/dm/dm.module.ts
import { Module } from '@nestjs/common';
import { DmService } from './dm.service';
import { DmGateway } from './dm.gateway';
import { SharedModule } from 'src/shared/shared.module';

@Module({
  imports: [SharedModule],
  providers: [DmService, DmGateway],
  exports: [DmService],
})
export class DmModule {}
