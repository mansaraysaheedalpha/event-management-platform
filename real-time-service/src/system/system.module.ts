import { Module } from '@nestjs/common';
import { SyncModule } from './sync/sync.module';
import { SyncController } from './sync/sync.controller';
import { PassportModule } from '@nestjs/passport';

@Module({
  imports: [SyncModule, PassportModule.register({ defaultStrategy: 'jwt' })],
  controllers: [SyncController], // <-- FIX: Moved from providers to controllers
  providers: [],
})
export class SystemModule {}
