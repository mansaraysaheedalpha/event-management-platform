import { WebSocketGateway, WebSocketServer } from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Inject, Logger, forwardRef } from '@nestjs/common';
import { SuggestionsService } from './suggestions.service';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class SuggestionsGateway {
  private readonly logger = new Logger(SuggestionsGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    @Inject(forwardRef(() => SuggestionsService))
    private readonly suggestionsService: SuggestionsService,
  ) {}

  public sendSuggestion(payload: any) {
    if (!payload.targetUserId) return;

    const userRoom = `user:${payload.targetUserId}`;
    // The event name is determined by the AI's payload type
    const eventName =
      payload.type === 'CONNECTION_SUGGESTION'
        ? 'suggestion.connection'
        : 'suggestion.circle';

    this.server.to(userRoom).emit(eventName, payload);
    this.logger.log(`Sent AI suggestion to user ${payload.targetUserId}`);
  }
}
