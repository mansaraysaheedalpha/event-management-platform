import { Module } from '@nestjs/common';
import { ContentService } from './content.service';
import { SharedModule } from 'src/shared/shared.module';

@Module({
  imports: [SharedModule],
  providers: [ContentService],
  exports: [ContentService],
})
export class ContentModule {}
