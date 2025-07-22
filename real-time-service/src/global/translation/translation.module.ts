import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TranslationService } from './translation.service';
import { TranslationGateway } from './translation.gateway';

@Module({
  imports: [ConfigModule], // Import ConfigModule as TranslationService uses it
  providers: [TranslationService, TranslationGateway],
})
export class TranslationModule {}
