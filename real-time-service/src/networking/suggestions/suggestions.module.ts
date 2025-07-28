import { Module } from '@nestjs/common';
import { SuggestionsService } from './suggestions.service';
import { SuggestionsGateway } from './suggestions.gateway';

@Module({
  providers: [SuggestionsService, SuggestionsGateway],
})
export class SuggestionsModule {}
