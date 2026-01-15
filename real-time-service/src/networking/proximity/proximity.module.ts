//src/networking/proximity/proximity.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { ProximityGateway } from './proximity.gateway';
import { ProximityService } from './proximity.service';
import { PrismaModule } from 'src/prisma.module';
import { SharedModule } from 'src/shared/shared.module';
import { ConnectionsModule } from '../connections/connections.module';
import { MatchingModule } from '../matching/matching.module';

@Module({
  imports: [
    PrismaModule,
    SharedModule,
    forwardRef(() => ConnectionsModule),
    MatchingModule,
  ],
  providers: [ProximityGateway, ProximityService],
  exports: [ProximityService],
})
export class ProximityModule {}
