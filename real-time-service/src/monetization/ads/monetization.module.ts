//src/monetization/ads/monetization.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { MonetizationService } from './monetization.service';
import { WaitlistModule } from '../waitlist/waitlist.module';
import { SponsorsModule } from '../sponsors/sponsors.module';
import { MonetizationGateway } from './monetization.gateway';
import { LeadsModule } from '../../leads/leads.module';

@Module({
  imports: [
    forwardRef(() => WaitlistModule),
    SponsorsModule,
    LeadsModule,
  ],
  providers: [MonetizationService, MonetizationGateway],
  exports: [MonetizationGateway],
})
export class MonetizationModule {}
