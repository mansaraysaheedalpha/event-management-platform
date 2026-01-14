//src/ops/backchannel/backchannel.module.ts
import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { BackchannelGateway } from './backchannel.gateway';
import { BackchannelService } from './backchannel.service';
import { BackchannelRoleService } from './backchannel-role.service';

@Module({
  imports: [HttpModule],
  providers: [BackchannelGateway, BackchannelService, BackchannelRoleService],
  exports: [BackchannelService, BackchannelRoleService],
})
export class BackchannelModule {}
