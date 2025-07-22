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

// All gateways can share the same port and namespace configuration
// We can centralize this configuration later.
@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class QnaGateway {
  private readonly logger = new Logger(QnaGateway.name);

  // We get a reference to the main server instance
  @WebSocketServer()
  server: Server;

  constructor(private readonly qnaService: QnaService) {}

  @SubscribeMessage('qa.question.ask')
  async handleAskQuestion(
    @MessageBody() dto: AskQuestionDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query; // Assuming sessionId is passed in query

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

      // A key part of a professional system: broadcasting to the correct rooms.
      const moderationRoom = `session:${sessionId}:moderation`;
      const publicRoom = `session:${sessionId}`;

      this.logger.log(
        `Broadcasting new question ${newQuestion.id} to rooms: ${publicRoom} and ${moderationRoom}`,
      );

      // Emit to moderators immediately.
      this.server.to(moderationRoom).emit('qa.question.new', newQuestion);

      // Based on your system rules, you might emit to the public room
      // only after a question is 'approved'. For now, we emit to both.
      this.server.to(publicRoom).emit('qa.question.new', newQuestion);

      // Return a success acknowledgment to the sender
      return { success: true, questionId: newQuestion.id };
    } catch (error) {
      this.logger.error(`Failed to ask question for user ${user.sub}:`, error);
      // In a real system, you'd use your getErrorMessage utility here
      return { success: false, error: 'Could not process your question.' };
    }
  }

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
        throw new Error(''); // without this check i get updatedQuestion is possibly null, you can help me replace it with something better
      }
      const publicRoom = `session:${sessionId}`;
      this.logger.log(
        `Broadcasting question update ${updatedQuestion.id} to room ${publicRoom}`,
      );

      // Broadcast the 'qna.question.updated' event with the full, updated question object.
      // Clients will listen for this event to update their UI in real-time.
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

      // Return specific, actionable errors to the client.
      return { success: false, error: (error as Error).message };
    }
  }

  @SubscribeMessage('qna.question.moderate')
  async handleModerateQuestion(
    @MessageBody() dto: ModerateQuestionDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    // --- WORLD-CLASS SECURITY CHECK ---
    // The user's permissions are decoded from the JWT by a prior middleware/guard.
    // We check for the specific permission required for this action.
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
        throw new Error(''); // without this check i get updatedQuestion is possibly null below, you can help me replace it with something better
      }
      const publicRoom = `session:${sessionId}`;
      const moderationRoom = `session:${sessionId}:moderation`;

      // Always update the moderators' view
      this.server
        .to(moderationRoom)
        .emit('qna.question.updated', updatedQuestion);

      // Broadcast intelligently to the public room
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
        // As per our spec, tell clients to remove the question from their UI
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
