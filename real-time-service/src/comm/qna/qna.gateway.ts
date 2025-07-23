import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger } from '@nestjs/common';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { QnaService } from './qna.service';
import { AskQuestionDto } from './dto/ask-question.dto';
import { UpvoteQuestionDto } from './dto/upvote-question.dto';
import { ModerateQuestionDto } from './dto/moderate-question.dto';

/**
 * WebSocket gateway for managing Q&A events during live sessions.
 * Handles asking, upvoting, and moderating questions in real-time.
 */
@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class QnaGateway {
  private readonly logger = new Logger(QnaGateway.name);

  @WebSocketServer()
  server: Server;

  constructor(private readonly qnaService: QnaService) {}

  /**
   * Handles incoming client requests to ask a new question.
   * Emits the new question to both public and moderator rooms.
   *
   * @param dto - Data transfer object with question content
   * @param client - Authenticated WebSocket client
   * @returns Result of question creation and broadcast
   */
  @SubscribeMessage('qa.question.ask')
  async handleAskQuestion(
    @MessageBody() dto: AskQuestionDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query;

    if (typeof sessionId !== 'string') {
      return { success: false, error: 'Session ID is required.' };
    }

    try {
      const newQuestion = await this.qnaService.askQuestion(
        user.sub,
        user.email,
        sessionId,
        dto,
      );

      const moderationRoom = `session:${sessionId}:moderation`;
      const publicRoom = `session:${sessionId}`;

      this.logger.log(
        `Broadcasting new question ${newQuestion.id} to rooms: ${publicRoom} and ${moderationRoom}`,
      );

      this.server.to(moderationRoom).emit('qa.question.new', newQuestion);
      this.server.to(publicRoom).emit('qa.question.new', newQuestion);

      return { success: true, questionId: newQuestion.id };
    } catch (error) {
      this.logger.error(`Failed to ask question for user ${user.sub}:`, error);
      return { success: false, error: 'Could not process your question.' };
    }
  }

  /**
   * Handles upvoting a question by a client.
   * Broadcasts the updated question to all participants in the session.
   *
   * @param dto - Data transfer object with questionId to upvote
   * @param client - Authenticated WebSocket client
   * @returns Updated upvote count or error response
   */
  @SubscribeMessage('qna.question.upvote')
  async handleUpvoteQuestion(
    @MessageBody() dto: UpvoteQuestionDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query;

    if (typeof sessionId !== 'string') {
      return { success: false, error: 'Session ID is required.' };
    }

    try {
      const updatedQuestion = await this.qnaService.upvoteQuestion(
        user.sub,
        dto,
      );

      if (!updatedQuestion) {
        return { success: false, error: 'Question not found or inactive.' };
      }

      const publicRoom = `session:${sessionId}`;
      this.logger.log(
        `Broadcasting question update ${updatedQuestion.id} to room ${publicRoom}`,
      );

      this.server.to(publicRoom).emit('qna.question.updated', updatedQuestion);

      return {
        success: true,
        questionId: updatedQuestion.id,
        upvotes: updatedQuestion._count.upvotes,
      };
    } catch (error) {
      this.logger.error(
        `Failed to upvote for user ${user.sub}:`,
        (error as Error).message,
      );
      return { success: false, error: (error as Error).message };
    }
  }

  /**
   * Handles moderation actions such as approving or dismissing a question.
   * Applies permission checks and broadcasts changes to public and moderator rooms.
   *
   * @param dto - Data transfer object with moderation details
   * @param client - Authenticated WebSocket client
   * @returns Moderation result including new status
   */
  @SubscribeMessage('qna.question.moderate')
  async handleModerateQuestion(
    @MessageBody() dto: ModerateQuestionDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    const requiredPermission = 'qna:moderate';
    if (!user.permissions || !user.permissions.includes(requiredPermission)) {
      this.logger.warn(
        `User ${user.sub} attempted to moderate without permission.`,
      );
      return {
        success: false,
        error: 'Forbidden: You do not have permission to perform this action.',
      };
    }

    try {
      const updatedQuestion = await this.qnaService.moderateQuestion(dto);

      if (!updatedQuestion) {
        return {
          success: false,
          error: 'Question not found or already handled.',
        };
      }

      const publicRoom = `session:${sessionId}`;
      const moderationRoom = `session:${sessionId}:moderation`;

      this.server
        .to(moderationRoom)
        .emit('qna.question.updated', updatedQuestion);

      if (updatedQuestion.status === 'approved') {
        this.logger.log(
          `Broadcasting approved question ${updatedQuestion.id} to public.`,
        );
        this.server
          .to(publicRoom)
          .emit('qna.question.updated', updatedQuestion);
      } else if (updatedQuestion.status === 'dismissed') {
        this.logger.log(
          `Broadcasting removed question ${updatedQuestion.id} to public.`,
        );
        this.server
          .to(publicRoom)
          .emit('qna.question.removed', { questionId: updatedQuestion.id });
      }

      return {
        success: true,
        questionId: updatedQuestion.id,
        newStatus: updatedQuestion.status,
      };
    } catch (error) {
      this.logger.error(
        `Failed to moderate question for user ${user.sub}:`,
        (error as Error).message,
      );
      return { success: false, error: (error as Error).message };
    }
  }
}
