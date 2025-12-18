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
import { ForbiddenException, forwardRef, Inject, Logger } from '@nestjs/common';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { ContentService } from './content.service';
import { ContentControlDto } from './dto/content-control.dto';
import { PresentationStateDto } from './dto/presentation-state.dto';
import { DropContentDto } from './dto/drop-content.dto';
import { PresentationStatusDto } from './dto/presentation-status.dto';
import { PrismaService } from 'src/prisma.service';
import { ChatService } from 'src/comm/chat/chat.service';
import { QnaService } from 'src/comm/qna/qna.service';
import { PollsService } from 'src/comm/polls/polls.service';
import { EventRegistrationValidationService } from 'src/shared/services/event-registration-validation.service';
import { SessionSettingsService } from 'src/shared/services/session-settings.service';

// Admin/moderator permissions that bypass registration checks
const ADMIN_PERMISSIONS = [
  'content:manage',
  'chat:moderate',
  'qna:moderate',
  'event:manage',
];

export interface RequestStateResponse {
  success: boolean;
  state: PresentationStateDto | null;
  error?: string;
}

interface ContentControlState {
  currentSlide: number;
  totalSlides: number;
  isActive: boolean;
  slideUrls: string[];
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
    @Inject(forwardRef(() => ChatService))
    private readonly chatService: ChatService,
    @Inject(forwardRef(() => QnaService))
    private readonly qnaService: QnaService,
    @Inject(forwardRef(() => PollsService))
    private readonly pollsService: PollsService,
    private readonly eventRegistrationValidationService: EventRegistrationValidationService,
    private readonly sessionSettingsService: SessionSettingsService,
  ) {}

  /**
   * Checks if user has any admin/moderator permissions that bypass registration checks.
   */
  private hasAdminPermissions(permissions: string[] | undefined): boolean {
    if (!permissions) return false;
    return permissions.some((p) => ADMIN_PERMISSIONS.includes(p));
  }

  @SubscribeMessage('session.join')
  async handleJoinSession(
    @MessageBody() data: { sessionId: string; eventId?: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ): Promise<{
    success: boolean;
    session?: {
      chatOpen: boolean;
      qaOpen: boolean;
      pollsOpen: boolean;
      chatEnabled: boolean;
      qaEnabled: boolean;
      pollsEnabled: boolean;
    };
    presentationState?: PresentationStateDto | null;
    error?: { message: string; statusCode: number };
  }> {
    if (!data.sessionId) {
      return {
        success: false,
        error: { message: 'Session ID is required.', statusCode: 400 },
      };
    }

    const user = getAuthenticatedUser(client);
    const sessionId = data.sessionId;

    // Determine the eventId - check message body first, then query params, then lookup
    let eventId = data.eventId || (client.handshake.query.eventId as string);

    this.logger.log(
      `[session.join] sessionId: ${sessionId}, eventId from body: ${data.eventId}, eventId from query: ${client.handshake.query.eventId}`,
    );

    if (!eventId) {
      // Look up eventId from session/chatSession as last resort
      const session = await this.prisma.chatSession.findFirst({
        where: { OR: [{ id: sessionId }, { eventId: sessionId }] },
        select: { eventId: true },
      });
      eventId = session?.eventId || sessionId;
      this.logger.log(`[session.join] eventId resolved from lookup/fallback: ${eventId}`);
    }

    // Check registration for non-admin users
    if (!this.hasAdminPermissions(user.permissions)) {
      this.logger.log(
        `[session.join] Validating registration for user ${user.sub} on event ${eventId}`,
      );
      const isRegistered =
        await this.eventRegistrationValidationService.isUserRegistered(
          user.sub,
          eventId,
        );

      if (!isRegistered) {
        this.logger.warn(
          `[session.join] User ${user.sub} denied - not registered for event ${eventId}`,
        );
        return {
          success: false,
          error: {
            message: 'You are not registered for this event.',
            statusCode: 403,
          },
        };
      }
      this.logger.log(
        `[session.join] User ${user.sub} registration validated for event ${eventId}`,
      );
    } else {
      this.logger.log(
        `[session.join] User ${user.sub} has admin permissions - skipping registration check`,
      );
    }

    const room = `session:${sessionId}`;
    await client.join(room);
    this.logger.log(`Client ${client.id} (user ${user.sub}) joined room: ${room}`);

    // Send chat history to the joining client
    try {
      const messages = await this.chatService.getSessionHistory(sessionId);
      client.emit('chat.history', { messages });
      this.logger.log(
        `Sent ${messages.length} chat history messages to client ${client.id}`,
      );
    } catch (error) {
      this.logger.error(
        `Failed to send chat history: ${getErrorMessage(error)}`,
      );
    }

    // Send Q&A history to the joining client
    try {
      const questions = await this.qnaService.getSessionQuestions(sessionId);
      client.emit('qa.history', { questions });
      this.logger.log(
        `Sent ${questions.length} Q&A questions to client ${client.id}`,
      );
    } catch (error) {
      this.logger.error(
        `Failed to send Q&A history: ${getErrorMessage(error)}`,
      );
    }

    // Send poll history to the joining client
    try {
      const polls = await this.pollsService.getSessionPolls(sessionId, user.sub);
      client.emit('poll.history', { polls });
      this.logger.log(
        `Sent ${polls.length} polls to client ${client.id}`,
      );
    } catch (error) {
      this.logger.error(
        `Failed to send poll history: ${getErrorMessage(error)}`,
      );
    }

    // Get session settings for the response
    const settings = await this.sessionSettingsService.getSessionSettings(sessionId);

    // Get current presentation state (if any) for the joining client
    let presentationState: PresentationStateDto | null = null;
    try {
      presentationState = await this.contentService.getPresentationState(sessionId);
      if (presentationState) {
        this.logger.log(
          `Sending presentation state to joining client: slide ${presentationState.currentSlide}/${presentationState.totalSlides}, active: ${presentationState.isActive}`,
        );
      }
    } catch (error) {
      this.logger.error(
        `Failed to get presentation state for joining client: ${getErrorMessage(error)}`,
      );
    }

    return {
      success: true,
      session: {
        chatEnabled: settings?.chat_enabled ?? true,
        qaEnabled: settings?.qa_enabled ?? true,
        pollsEnabled: settings?.polls_enabled ?? true,
        chatOpen: settings?.chat_open ?? false,
        qaOpen: settings?.qa_open ?? false,
        pollsOpen: settings?.polls_open ?? false,
      },
      presentationState,
    };
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
      const payload: ContentControlState = {
        currentSlide: newState.currentSlide,
        totalSlides: newState.totalSlides,
        isActive: newState.isActive,
        slideUrls: newState.slideUrls || [],
      };

      this.server.to(publicRoom).emit(eventName, payload);
      this.logger.log(
        `Broadcasted 'slide.update' to room ${publicRoom} with slide: ${newState.currentSlide}, slideUrls: ${payload.slideUrls.length} slides`,
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
