//src/permissions/permissions.module
import { Module } from '@nestjs/common';
import { PermissionsService } from './permissions.service';
import { PrismaModule } from 'src/prisma.module';
import { SharedModule } from 'src/shared/shared.module';

@Module({
  imports: [PrismaModule, SharedModule],
  providers: [PermissionsService],
  exports: [PermissionsService],
})
export class PermissionsModule {}
