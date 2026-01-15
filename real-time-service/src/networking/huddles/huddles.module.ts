//src/networking/huddles/huddles.module.ts
import { Module } from '@nestjs/common';
import { PrismaModule } from 'src/prisma.module';
import { SharedModule } from 'src/shared/shared.module';
import { HuddlesService } from './huddles.service';
import { HuddlesGateway } from './huddles.gateway';

@Module({
  imports: [PrismaModule, SharedModule],
  providers: [HuddlesService, HuddlesGateway],
  exports: [HuddlesService],
})
export class HuddlesModule {}
