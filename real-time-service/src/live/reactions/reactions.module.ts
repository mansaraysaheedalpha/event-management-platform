//src/live/reactions/reactions.module.ts
import { Module } from '@nestjs/common';
import { ReactionsService } from './reactions.service';
import { ReactionsGateway } from './reactions.gateway';
import { SharedModule } from 'src/shared/shared.module';

@Module({
  imports: [SharedModule],
  providers: [ReactionsService, ReactionsGateway],
})
export class ReactionsModule {}
