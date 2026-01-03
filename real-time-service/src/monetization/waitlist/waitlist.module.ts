//src/monetization/waitlist/waitlist.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { WaitlistService } from './waitlist.service';
import { MonetizationModule } from '../ads/monetization.module';

@Module({
  imports: [forwardRef(() => MonetizationModule)],
  providers: [WaitlistService],
  exports: [WaitlistService],
})
export class WaitlistModule {}
