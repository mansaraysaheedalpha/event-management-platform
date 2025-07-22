import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { ForbiddenException, Logger } from '@nestjs/common';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { ContentService } from './content.service';
import { ContentControlDto } from './dto/content-control.dto';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class ContentGateway {
  private readonly logger = new Logger(ContentGateway.name);
  @WebSocketServer() server: Server;

  constructor(private readonly contentService: ContentService) {}

  /**
   * Handles control commands from a presenter (e.g., next slide).
   */
  @SubscribeMessage('content.control')
  async handleContentControl(
    @MessageBody() dto: ContentControlDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    // --- Permission Check ---
    const requiredPermission = 'content:manage';
    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to control content.',
      );
    }

    try {
      const newState = await this.contentService.controlPresentation(
        sessionId,
        dto,
      );

      const publicRoom = `session:${sessionId}`;
      const eventName = 'slide.update';

      // Broadcast the new, simplified state to all attendees.
      // We don't need to send the full list of slide URLs every time.
      const payload = {
        currentSlide: newState.currentSlide,
        totalSlides: newState.totalSlides,
        isActive: newState.isActive,
      };

      this.server.to(publicRoom).emit(eventName, payload);
      this.logger.log(
        `Broadcasted slide update for session ${sessionId}: slide ${newState.currentSlide}`,
      );

      return { success: true, newState: payload };
    } catch (error) {
      this.logger.error(
        `Failed to control content for user ${user.sub}:`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Handles requests from new attendees to get the current presentation state.
   */
  @SubscribeMessage('content.request_state')
  async handleRequestState(@ConnectedSocket() client: AuthenticatedSocket) {
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const state = await this.contentService.getPresentationState(sessionId);

      if (!state) {
        return { success: true, state: null }; // No active presentation
      }

      // Return the full state, including slide URLs, directly to the requester.
      return { success: true, state };
    } catch (error) {
      this.logger.error(
        `Failed to get presentation state for session ${sessionId}:`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }
}
