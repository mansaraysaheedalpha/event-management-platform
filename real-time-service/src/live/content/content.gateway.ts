//src/content/content.gateway.ts
import { PresentationState } from 'src/common/interfaces/presentation-state.interface';
export interface RequestStateResponse {
  success: boolean;
  state: PresentationState | null;
  error?: string;
}
interface ContentControlState {
  currentSlide: number;
  totalSlides: number;
  isActive: boolean;
}

interface ContentControlResponse {
  success: boolean;
  newState?: ContentControlState;
  error?: string;
}
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
import { DropContentDto } from './dto/drop-content.dto';
import { PrismaService } from 'src/prisma.service';

/**
 * Gateway handling WebSocket communication for live content control
 * such as navigating presentation slides.
 *
 * WebSocket namespace: `/events`
 * Main broadcast event: `slide.update`
 *
 * Usage:
 *  - Presenter sends `content.control` with action like `NEXT_SLIDE`
 *  - Attendees send `content.request_state` to sync state on join
 *  - Clients listen for `slide.update` events in the room `session:{sessionId}`
 */
@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class ContentGateway {
  private readonly logger = new Logger(ContentGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    private readonly contentService: ContentService,
    private readonly prisma: PrismaService,
  ) {}

  /**
   * Handles control commands from a presenter (e.g., next slide).
   *
   * @param dto - Data describing the control action.
   * @param client - The authenticated socket connection.
   * @returns {Promise<ContentControlResponse>} Success flag and the new state or error.
   * @throws ForbiddenException if the user lacks permission to control content.
   */
  @SubscribeMessage('content.control')
  async handleContentControl(
    @MessageBody() dto: ContentControlDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ): Promise<ContentControlResponse> {
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
   *
   * @param client - The authenticated socket connection.
   * @returns {Promise<RequestStateResponse>} The full presentation state or error. Returns state as null if no presentation is running.
   */
  @SubscribeMessage('content.request_state')
  async handleRequestState(
    @ConnectedSocket() client: AuthenticatedSocket,
  ): Promise<RequestStateResponse> {
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
      return { success: false, state: null, error: getErrorMessage(error) };
    }
  }

  /**
   * Handles a presenter dropping content for all attendees in a session.
   */
  @SubscribeMessage('content.drop')
  async handleContentDrop(
    @MessageBody() dto: DropContentDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    const requiredPermission = 'content:manage';
    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to drop content.',
      );
    }

    try {
      // --- THIS IS THE REAL IMPLEMENTATION ---
      // Fetch the dropper's name from our local UserReference table.
      const dropperDetails = await this.prisma.userReference.findUnique({
        where: { id: user.sub },
        select: { firstName: true, lastName: true },
      });
      const dropper = {
        id: user.sub,
        name: `${dropperDetails?.firstName || 'Event'} ${dropperDetails?.lastName || 'Staff'}`,
      };
      // --- END OF REAL IMPLEMENTATION ---

      const contentPayload = await this.contentService.handleContentDrop(
        dto,
        dropper,
        sessionId,
      );

      const publicRoom = `session:${sessionId}`;
      const eventName = 'content.dropped'; // A more specific event name

      this.server.to(publicRoom).emit(eventName, contentPayload);
      this.logger.log(`Broadcasted content drop to room ${publicRoom}`);

      return { success: true };
    } catch (error) {
      this.logger.error(
        `Failed to drop content for user ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }
}
