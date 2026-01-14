//src/networking/proximity/proximity.module.ts
import { Module } from '@nestjs/common';
import { ProximityGateway } from './proximity.gateway';
import { ProximityService } from './proximity.service';
import { PrismaModule } from 'src/prisma.module';
import { SharedModule } from 'src/shared/shared.module';

@Module({
  imports: [PrismaModule, SharedModule],
  providers: [ProximityGateway, ProximityService],
  exports: [ProximityService],
})
export class ProximityModule {}
