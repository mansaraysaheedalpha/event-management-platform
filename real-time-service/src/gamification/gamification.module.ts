import { Module } from '@nestjs/common';
import { GamificationService } from './gamification.service';
import { GamificationGateway } from './gamification.gateway';

@Module({
  providers: [GamificationService, GamificationGateway],
  exports: [GamificationService],
})
export class GamificationModule {}
