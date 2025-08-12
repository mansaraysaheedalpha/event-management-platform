//src/comm/dm/dm.module.ts
import { Module } from '@nestjs/common';
import { DmService } from './dm.service';

@Module({
  providers: [DmService],
  exports: [DmService],
})
export class DmModule {}
