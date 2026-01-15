//src/networking/matching/matching.module.ts
import { Module } from '@nestjs/common';
import { MatchingService } from './matching.service';
import { PrismaModule } from 'src/prisma.module';

@Module({
  imports: [PrismaModule],
  providers: [MatchingService],
  exports: [MatchingService],
})
export class MatchingModule {}
