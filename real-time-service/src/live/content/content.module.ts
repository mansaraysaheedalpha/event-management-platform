import { Module } from '@nestjs/common';
import { ContentService } from './content.service';
import { ContentGateway } from './content.gateway';

@Module({
  providers: [ContentService, ContentGateway], // We'll fill the gateway in next
})
export class ContentModule {}
