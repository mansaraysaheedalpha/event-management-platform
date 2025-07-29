import { Module } from '@nestjs/common';
import { MonetizationService } from './monetization.service';
import { WaitlistModule } from '../waitlist/waitlist.module';
import { SponsorsModule } from '../sponsors/sponsors.module';
import { MonetizationGateway } from './monetization.gateway';

@Module({
  imports: [WaitlistModule, SponsorsModule],
  providers: [MonetizationService, MonetizationGateway],
})
export class MonetizationModule {}
