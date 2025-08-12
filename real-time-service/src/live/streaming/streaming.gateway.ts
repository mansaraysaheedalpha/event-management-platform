//src/live/streaming/streaming.gateway.ts
import { WebSocketGateway, WebSocketServer } from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger } from '@nestjs/common';
import { SubtitleChunkDto } from './dto/subtitle-chunk.dto';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class StreamingGateway {
  private readonly logger = new Logger(StreamingGateway.name);
  @WebSocketServer() server: Server;

  public broadcastSubtitleChunk(payload: SubtitleChunkDto) {
    const sessionRoom = `session:${payload.sessionId}`;
    const eventName = 'subtitle.stream.chunk';
    this.server.to(sessionRoom).emit(eventName, payload);
  }
}
