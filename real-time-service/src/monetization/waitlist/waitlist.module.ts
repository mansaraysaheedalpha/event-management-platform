//src/monetization/waitlist/waitlist.module.ts
import { Module } from '@nestjs/common';
import { WaitlistService } from './waitlist.service';

@Module({
  providers: [WaitlistService],
  exports: [WaitlistService],
})
export class WaitlistModule {}
