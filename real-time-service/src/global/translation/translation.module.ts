import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TranslationService } from './translation.service';

@Module({
  imports: [ConfigModule], // Import ConfigModule as TranslationService uses it
  providers: [TranslationService],
  exports: [TranslationService],
})
export class TranslationModule {}
