//src/monetization/waitlist/waitlist.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { WaitlistService } from './waitlist.service';
import { MonetizationModule } from '../ads/monetization.module';
import { GamificationModule } from 'src/gamification/gamification.module';

@Module({
  imports: [forwardRef(() => MonetizationModule), GamificationModule],
  providers: [WaitlistService],
  exports: [WaitlistService],
})
export class WaitlistModule {}
