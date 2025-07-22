import { Module } from '@nestjs/common';
import { ReactionsService } from './reactions.service';
import { ReactionsGateway } from './reactions.gateway';

@Module({
  providers: [ReactionsService, ReactionsGateway],
})
export class ReactionsModule {}
