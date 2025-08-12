//src/system/system.module.ts
import { Module } from '@nestjs/common';
import { SyncModule } from './sync/sync.module';
import { SyncController } from './sync/sync.controller';
import { PassportModule } from '@nestjs/passport';
import { ConnectionModule } from './connection/connection.module';
import { SyncGateway } from './sync/sync.gateway';

@Module({
  imports: [
    SyncModule,
    PassportModule.register({ defaultStrategy: 'jwt' }),
    ConnectionModule,
  ],
  controllers: [SyncController],
  providers: [SyncGateway],
})
export class SystemModule {}
