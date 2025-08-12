//src/networking/proximity/proximity.module.ts
import { Module } from '@nestjs/common';
import { ProximityService } from './proximity.service';
import { PrismaModule } from 'src/prisma.module';

@Module({
  imports: [PrismaModule],
  providers: [ProximityService],
  exports: [ProximityService],
})
export class ProximityModule {}
