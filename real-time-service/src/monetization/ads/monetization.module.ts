//src/monetization/ads/monetization.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { MonetizationService } from './monetization.service';
import { WaitlistModule } from '../waitlist/waitlist.module';
import { SponsorsModule } from '../sponsors/sponsors.module';
import { MonetizationGateway } from './monetization.gateway';

@Module({
  imports: [forwardRef(() => WaitlistModule), SponsorsModule],
  providers: [MonetizationService, MonetizationGateway],
  exports: [MonetizationGateway],
})
export class MonetizationModule {}
