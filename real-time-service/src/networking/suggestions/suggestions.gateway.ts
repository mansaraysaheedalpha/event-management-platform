//src/networking/suggestions/suggestions.gateway.ts
import { WebSocketGateway, WebSocketServer } from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger } from '@nestjs/common';

// Define the shape of the payload we expect from the Oracle AI
export interface AiSuggestionPayload {
  type: 'CONNECTION_SUGGESTION' | 'CIRCLE_SUGGESTION';
  targetUserId: string;
  // ... other properties from the AI can exist here
}

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class SuggestionsGateway {
  private readonly logger = new Logger(SuggestionsGateway.name);
  @WebSocketServer() server: Server;

  constructor() {}

  /**
   * Listens for internal AI suggestion events and broadcasts them to the target user.
   */
  sendSuggestion(payload: AiSuggestionPayload) {
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
