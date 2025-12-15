//src/comm/chat/chat.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { HttpException, Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { ChatService } from './chat.service';
import { SendMessageDto } from './dto/send-message.dto';
import { EditMessageDto } from './dto/edit-message.dto';
import { DeleteMessageDto } from './dto/delete-message.dto';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { ReactToMessageDto } from './dto/react-to-message.dto';
import { Throttle } from '@nestjs/throttler';
import { EventRegistrationValidationService } from 'src/shared/services/event-registration-validation.service';
import { SessionSettingsService } from 'src/shared/services/session-settings.service';

// Admin/moderator permissions that bypass registration checks
const ADMIN_PERMISSIONS = [
  'content:manage',
  'chat:moderate',
  'qna:moderate',
  'event:manage',
];

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class ChatGateway {
  private readonly logger = new Logger(ChatGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    private readonly chatService: ChatService,
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

  /**
   * Validates that a non-admin user is registered for the event.
   * Returns an error response object if not registered, null otherwise.
   */
  private async validateRegistration(
    userId: string,
    eventId: string,
    permissions: string[] | undefined,
  ): Promise<{ success: false; error: { message: string; statusCode: number } } | null> {
    if (this.hasAdminPermissions(permissions)) {
      return null; // Admin users bypass registration check
    }

    const isRegistered =
      await this.eventRegistrationValidationService.isUserRegistered(
        userId,
        eventId,
      );

    if (!isRegistered) {
      this.logger.warn(
        `[Chat] User ${userId} denied - not registered for event ${eventId}`,
      );
      return {
        success: false,
        error: {
          message: 'You are not registered for this event.',
          statusCode: 403,
        },
      };
    }

    return null; // User is registered
  }

  /**
   * Validates that chat is active for the session.
   * - If chat_enabled is false: Block everyone (feature completely disabled)
   * - If chat_open is false: Block attendees, but allow organizers/speakers (bypass)
   * - If both are true: Allow everyone
   *
   * @param sessionId - The session ID to check
   * @param permissions - Optional user permissions to check for bypass
   * @returns Error response if blocked, null if allowed
   */
  private async validateChatActive(
    sessionId: string,
    permissions?: string[],
  ): Promise<{ success: false; error: { message: string; statusCode: number } } | null> {
    const settings = await this.sessionSettingsService.getSessionSettings(sessionId);

    // If chat feature is completely disabled, block everyone (no bypass)
    if (!settings?.chat_enabled) {
      this.logger.warn(`[Chat] Chat is disabled for session ${sessionId}`);
      return {
        success: false,
        error: {
          message: 'Chat is disabled for this session.',
          statusCode: 403,
        },
      };
    }

    // If chat is closed, check if user has organizer/speaker permissions to bypass
    if (!settings?.chat_open) {
      // Organizers and speakers (with admin permissions) can bypass the chat_open check
      if (this.hasAdminPermissions(permissions)) {
        this.logger.log(
          `[Chat] Chat is closed for session ${sessionId}, but user has admin permissions - allowing bypass`,
        );
        return null; // Allow the message through
      }

      this.logger.warn(`[Chat] Chat is closed for session ${sessionId}`);
      return {
        success: false,
        error: {
          message: 'Chat is currently closed for this session.',
          statusCode: 403,
        },
      };
    }

    return null; // Chat is enabled and open
  }

  /**
   * Handles incoming 'chat.message.send' events.
   * Sends a message to the specified session and broadcasts it to all participants.
   *
   * @param dto - The message payload sent by the client.
   * @param client - The connected WebSocket client (with authentication).
   * @returns An object containing success status and message ID or error.
   */
  @Throttle({
    default: { limit: 100, ttl: 60000 },
    vip: { limit: 500, ttl: 60000 },
  }) // Apply specific limits for this action
  @SubscribeMessage('chat.message.send')
  async handleSendMessage(
    @MessageBody() dto: SendMessageDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = dto; // sessionId from DTO = which chat session
    // eventId from query params = parent event for dashboard analytics
    const eventId = (client.handshake.query.eventId as string) || sessionId;

    // Validate event registration for non-admin users
    const registrationError = await this.validateRegistration(
      user.sub,
      eventId,
      user.permissions,
    );
    if (registrationError) return registrationError;

    // Validate that chat is enabled AND open for this session
    // Pass permissions so organizers/speakers can bypass the chat_open check
    const chatActiveError = await this.validateChatActive(sessionId, user.permissions);
    if (chatActiveError) return chatActiveError;

    this.logger.log(
      `📨 Received chat.message.send from user ${user.sub} for session ${sessionId}, eventId ${eventId}`,
    );

    try {
      const newMessage = (await this.chatService.sendMessage(
        user.sub,
        sessionId, // The chat session ID
        dto,
        eventId, // Pass eventId for dashboard analytics
      )) as { id: string };

      const publicRoom = `session:${sessionId}`;
      this.server.to(publicRoom).emit('chat.message.new', newMessage);

      this.logger.log(
        `✅ Message ${newMessage.id} sent successfully, broadcasted to ${publicRoom}`,
      );

      return { success: true, messageId: newMessage.id };
    } catch (error) {
      this.logger.error(
        `❌ Failed to send message for user ${user.sub}:`,
        getErrorMessage(error),
      );
      if (error instanceof HttpException) {
        return {
          success: false,
          error: { message: error.message, statusCode: error.getStatus() },
        };
      }
      return { success: false, error: 'An internal server error occurred.' };
    }
  }

  /**
   * Handles 'chat.message.edit' events.
   * Edits an existing message and emits the updated message to the session.
   *
   * @param dto - The edit payload including messageId and new content.
   * @param client - The authenticated WebSocket client.
   * @returns An object with success status and updated message ID or error.
   */
  @SubscribeMessage('chat.message.edit')
  async handleEditMessage(
    @MessageBody() dto: EditMessageDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = dto; // Read sessionId from DTO body

    try {
      const editedMessage = (await this.chatService.editMessage(
        user.sub,
        dto,
      )) as { id: string };
      const publicRoom = `session:${sessionId}`;
      this.server.to(publicRoom).emit('chat.message.updated', editedMessage);
      return { success: true, messageId: editedMessage.id };
    } catch (error) {
      this.logger.error(
        `Failed to edit message for user ${user.sub}:`,
        getErrorMessage(error),
      );
      if (error instanceof HttpException) {
        return {
          success: false,
          error: { message: error.message, statusCode: error.getStatus() },
        };
      }
      return { success: false, error: 'An internal server error occurred.' };
    }
  }

  /**
   * Handles 'chat.message.delete' events.
   * Deletes a message (based on user permissions) and notifies the session participants.
   *
   * @param dto - Payload containing the messageId to be deleted.
   * @param client - The authenticated client attempting deletion.
   * @returns An object with deletion status and deleted message ID or error.
   */
  @SubscribeMessage('chat.message.delete')
  async handleDeleteMessage(
    @MessageBody() dto: DeleteMessageDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      // The service handles the complex permission logic
      const deleteResult = await this.chatService.deleteMessage(
        user.sub,
        dto,
        user.permissions,
      );

      const publicRoom = `session:${deleteResult.sessionId}`;
      const payload = { messageId: deleteResult.deletedMessageId };
      this.server.to(publicRoom).emit('chat.message.deleted', payload);

      return { success: true, deletedMessageId: deleteResult.deletedMessageId };
    } catch (error) {
      this.logger.error(
        `Failed to delete message for user ${user.sub}:`,
        getErrorMessage(error),
      );
      if (error instanceof HttpException) {
        return {
          success: false,
          error: { message: error.message, statusCode: error.getStatus() },
        };
      }
      return { success: false, error: 'An internal server error occurred.' };
    }
  }

  /**
   * Handles a user reacting to a specific message.
   */
  @SubscribeMessage('chat.message.react')
  async handleReactToMessage(
    @MessageBody() dto: ReactToMessageDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = dto; // Read sessionId from DTO body
    // eventId from query params = parent event for dashboard analytics
    const eventId = (client.handshake.query.eventId as string) || sessionId;

    // Validate event registration for non-admin users
    const registrationError = await this.validateRegistration(
      user.sub,
      eventId,
      user.permissions,
    );
    if (registrationError) return registrationError;

    // Validate that chat is enabled AND open for this session
    // Pass permissions so organizers/speakers can bypass the chat_open check
    const chatActiveError = await this.validateChatActive(sessionId, user.permissions);
    if (chatActiveError) return chatActiveError;

    try {
      const updatedMessageWithReactions: {
        id: string;
        [key: string]: any;
      } | null = await this.chatService.reactToMessage(user.sub, dto, eventId);

      if (updatedMessageWithReactions) {
        const publicRoom = `session:${sessionId}`;
        const eventName = 'chat.message.updated';

        // Broadcast the fully updated message with the new reaction summary
        this.server.to(publicRoom).emit(eventName, updatedMessageWithReactions);
        this.logger.log(
          `Broadcasted reaction update for message ${dto.messageId} to room ${publicRoom}`,
        );
      }

      return { success: true, messageId: dto.messageId };
    } catch (error) {
      this.logger.error(
        `Failed to process reaction for user ${user.sub}:`,
        getErrorMessage(error),
      );
      if (error instanceof HttpException) {
        return {
          success: false,
          error: { message: error.message, statusCode: error.getStatus() },
        };
      }
      return { success: false, error: 'An internal server error occurred.' };
    }
  }

  /**
   * Handles Redis events for chat status changes.
   * Broadcasts the status change to all clients in the session room.
   */
  @OnEvent('platform.sessions.chat.v1')
  handleChatStatusChange(payload: {
    sessionId: string;
    chatOpen: boolean;
    eventId: string;
  }) {
    const { sessionId, chatOpen } = payload;
    const publicRoom = `session:${sessionId}`;

    this.server.to(publicRoom).emit('chat.status.changed', {
      sessionId,
      isOpen: chatOpen,
    });

    // Clear cached settings so next validation fetches fresh data
    this.sessionSettingsService.clearCache(sessionId);

    this.logger.log(
      `📢 Broadcasted chat.status.changed (isOpen: ${chatOpen}) to room ${publicRoom}`,
    );
  }
}
