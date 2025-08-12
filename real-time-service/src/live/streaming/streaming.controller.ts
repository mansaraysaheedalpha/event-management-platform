//src/live/streaming/streaming.controller.ts
import { Body, Controller, Post, UseGuards } from '@nestjs/common';
import { InternalApiKeyGuard } from 'src/common/guards/internal-api-key.guard';
import { StreamingGateway } from './streaming.gateway';
import { SubtitleChunkDto } from './dto/subtitle-chunk.dto';

@Controller('internal/stream')
@UseGuards(InternalApiKeyGuard) // Secure this endpoint for internal use only
export class StreamingController {
  constructor(private readonly streamingGateway: StreamingGateway) {}

  @Post('subtitles')
  handleSubtitleChunk(@Body() subtitleChunk: SubtitleChunkDto) {
    this.streamingGateway.broadcastSubtitleChunk(subtitleChunk);
    // Respond immediately with 202 Accepted
    return { status: 'accepted' };
  }
}
