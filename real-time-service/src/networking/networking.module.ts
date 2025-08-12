//src/networking/networking.module.ts
import { Module } from '@nestjs/common';
import { CirclesModule } from './circles/circles.module';
import { SuggestionsModule } from './suggestions/suggestions.module';
import { ProximityModule } from './proximity/proximity.module';

@Module({
  imports: [CirclesModule, SuggestionsModule, ProximityModule],
})
export class NetworkingModule {}
