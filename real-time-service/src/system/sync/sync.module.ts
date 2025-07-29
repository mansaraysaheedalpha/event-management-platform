import { Module } from '@nestjs/common';
import { SyncService } from './sync.service';
import { SyncGateway } from './sync.gateway';

@Module({
  imports: [],
  providers: [SyncService, SyncGateway],
  exports: [SyncService],
})
export class SyncModule {}
