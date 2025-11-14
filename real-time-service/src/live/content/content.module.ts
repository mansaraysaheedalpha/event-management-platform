//src/content/content.module.ts
import { Module } from '@nestjs/common';
import { ContentService } from './content.service';
import { SharedModule } from 'src/shared/shared.module';
import { ContentGateway } from './content.gateway';

@Module({
  imports: [SharedModule],
  providers: [ContentGateway, ContentService],
  exports: [ContentService],
})
export class ContentModule {}
