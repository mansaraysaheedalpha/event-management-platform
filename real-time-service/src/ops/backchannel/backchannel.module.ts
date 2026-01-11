//src/ops/backchannel/backchannel.module.ts
import { Module } from '@nestjs/common';
import { BackchannelGateway } from './backchannel.gateway';
import { BackchannelService } from './backchannel.service';

@Module({
  providers: [BackchannelGateway, BackchannelService],
  exports: [BackchannelService],
})
export class BackchannelModule {}
