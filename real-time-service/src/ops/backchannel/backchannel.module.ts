//src/ops/backchannel/backchannel.module.ts
import { Module } from '@nestjs/common';
import { BackchannelService } from './backchannel.service';

@Module({
  providers: [BackchannelService],
  exports: [BackchannelService],
})
export class BackchannelModule {}
