import { Module } from '@nestjs/common';
import { SyncService } from './sync.service';
import { SyncGateway } from './sync.gateway';
import { SyncController } from './sync.controller';

@Module({
  providers: [SyncService, SyncGateway, SyncController],
})
export class SyncModule {}
