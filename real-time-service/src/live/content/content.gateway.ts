//src/content/content.gateway.ts
import { PresentationState } from 'src/common/interfaces/presentation-state.interface';
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { OnEvent } from '@nestjs/event-emitter';
import { Server } from 'socket.io';
import { ForbiddenException, Logger } from '@nestjs/common';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { ContentService } from './content.service';
import { ContentControlDto } from './dto/content-control.dto';
import { PresentationStateDto } from './dto/presentation-state.dto';
import { DropContentDto } from './dto/drop-content.dto';
import { PresentationStatusDto } from './dto/presentation-status.dto';
import { PrismaService } from 'src/prisma.service';

export interface RequestStateResponse {
  success: boolean;
  state: PresentationStateDto | null;
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

  @SubscribeMessage('session.join')
  handleJoinSession(
    @MessageBody() data: { sessionId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ): void {
    if (data.sessionId) {
      const room = `session:${data.sessionId}`;
      client.join(room);
      this.logger.log(`Client ${client.id} joined room: ${room}`);
    }
  }

  // --- NEW: Method to handle clients leaving a session room ---
  @SubscribeMessage('session.leave')
  handleLeaveSession(
    @MessageBody() data: { sessionId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ): void {
    if (data.sessionId) {
      const room = `session:${data.sessionId}`;
      client.leave(room);
      this.logger.log(`Client ${client.id} left room: ${room}`);
    }
  }

  @OnEvent('presentation-events')
  async handlePresentationStatusUpdate(payload: PresentationStatusDto) {
    const userRoom = `user:${payload.userId}`;
    this.server.to(userRoom).emit('presentation.status.update', {
      sessionId: payload.sessionId,
      status: payload.status,
    });
    this.logger.log(`Sent targeted presentation status to room ${userRoom}`);
  }

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
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = dto; // <-- READ from the message body

    this.logger.log(
      `[ContentGateway] Received 'content.control' for session ${sessionId} with action: ${dto.action}`,
    );

    const requiredPermission = 'content:manage';
    if (!user.permissions?.includes(requiredPermission)) {
      this.logger.warn(
        `User ${user.sub} forbidden to control content for session ${sessionId}.`,
      );
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
      const payload = {
        currentSlide: newState.currentSlide,
        totalSlides: newState.totalSlides,
        isActive: newState.isActive,
      };

      this.server.to(publicRoom).emit(eventName, payload);
      this.logger.log(
        `Broadcasted 'slide.update' to room ${publicRoom} with slide: ${newState.currentSlide}`,
      );
      return { success: true, newState: payload };
    } catch (error) {
      this.logger.error(
        `Error in handleContentControl for session ${sessionId}:`,
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
    @MessageBody() data: { sessionId: string },
  ): Promise<RequestStateResponse> {
    // <-- The return type is now strongly-typed
    const { sessionId } = data;
    try {
      const state = await this.contentService.getPresentationState(sessionId);
      return { success: true, state: state || null };
    } catch (error) {
      this.logger.error(
        `Failed to get state for session ${sessionId}:`,
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
      const dropperDetails = await this.prisma.userReference.findUnique({
        where: { id: user.sub },
        select: { firstName: true, lastName: true },
      });
      const dropper = {
        id: user.sub,
        name: `${dropperDetails?.firstName || 'Event'} ${
          dropperDetails?.lastName || 'Staff'
        }`,
      };

      const contentPayload = await this.contentService.handleContentDrop(
        dto,
        dropper,
        sessionId,
      );
      const publicRoom = `session:${sessionId}`;
      const eventName = 'content.dropped';
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
