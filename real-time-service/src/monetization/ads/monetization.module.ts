import { Module } from '@nestjs/common';
import { MonetizationService } from './monetization.service';
import { MonetizationGateway } from './monetization.gateway';
import { WaitlistModule } from '../waitlist/waitlist.module';

@Module({
  imports: [WaitlistModule], // <-- Add WaitlistModule
  providers: [MonetizationService, MonetizationGateway],
  exports: [MonetizationService],
})
export class MonetizationModule {}
