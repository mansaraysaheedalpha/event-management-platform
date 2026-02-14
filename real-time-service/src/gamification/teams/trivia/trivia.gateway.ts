// src/gamification/teams/trivia/trivia.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { ForbiddenException, Logger } from '@nestjs/common';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { TriviaService } from './trivia.service';
import { GamificationService } from '../../gamification.service';
import { TeamNotificationsService } from '../notifications/team-notifications.service';
import { PrismaService } from 'src/prisma.service';
import { CreateTriviaGameDto } from './dto/create-trivia-game.dto';
import { StartTriviaDto } from './dto/start-trivia.dto';
import { AdvanceTriviaDto } from './dto/advance-trivia.dto';
import { EndTriviaDto } from './dto/end-trivia.dto';
import { DeleteTriviaDto } from './dto/delete-trivia.dto';
import { SubmitTriviaAnswerDto } from './dto/submit-trivia-answer.dto';

// Permissions that allow trivia management (organizers/admins)
const TRIVIA_ADMIN_PERMISSIONS = [
  'event:manage',
  'content:manage',
  'gamification:manage',
];

// In-memory map of question activation timestamps for speed bonus calculation
// Key: questionId, Value: activation time (ms since epoch)
// Entries cleaned on advance (per-question) and endGame (bulk).
const questionActivationTimes = new Map<string, number>();
// Track which questionIds belong to which gameId for bulk cleanup on endGame
const gameQuestionIds = new Map<string, Set<string>>();

// Safety sweep: remove activation entries older than 2 hours (abandoned games)
const ACTIVATION_TTL_MS = 2 * 60 * 60 * 1000;
setInterval(() => {
  const cutoff = Date.now() - ACTIVATION_TTL_MS;
  for (const [qId, time] of questionActivationTimes) {
    if (time < cutoff) questionActivationTimes.delete(qId);
  }
  for (const [gId, qIds] of gameQuestionIds) {
    for (const qId of qIds) {
      if (!questionActivationTimes.has(qId)) qIds.delete(qId);
    }
    if (qIds.size === 0) gameQuestionIds.delete(gId);
  }
}, 10 * 60 * 1000).unref(); // .unref() so it doesn't prevent process exit

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class TriviaGateway {
  private readonly logger = new Logger(TriviaGateway.name);

  @WebSocketServer()
  server: Server;

  constructor(
    private readonly triviaService: TriviaService,
    private readonly gamificationService: GamificationService,
    private readonly teamNotificationsService: TeamNotificationsService,
    private readonly prisma: PrismaService,
  ) {}

  // ─── Authorization ──────────────────────────────────────────

  private assertOrganizerPermissions(client: AuthenticatedSocket) {
    const user = getAuthenticatedUser(client);
    const hasPermission = user.permissions?.some((p: string) =>
      TRIVIA_ADMIN_PERMISSIONS.includes(p),
    );
    if (!hasPermission) {
      throw new ForbiddenException(
        'You do not have permission to manage trivia games.',
      );
    }
  }

  // ─── Organizer: Create Game ─────────────────────────────────

  @SubscribeMessage('trivia.create')
  async handleCreateGame(
    @MessageBody() dto: CreateTriviaGameDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      this.assertOrganizerPermissions(client);
      const game = await this.triviaService.createGame(
        user.sub,
        sessionId,
        dto,
      );

      return {
        event: 'trivia.create.response',
        data: { success: true, game },
      };
    } catch (error) {
      this.logger.error(
        `Failed to create trivia game: ${getErrorMessage(error)}`,
      );
      return {
        event: 'trivia.create.response',
        data: { success: false, error: getErrorMessage(error) },
      };
    }
  }

  // ─── Organizer: Delete Draft Game ──────────────────────────

  @SubscribeMessage('trivia.delete')
  async handleDeleteGame(
    @MessageBody() dto: DeleteTriviaDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      this.assertOrganizerPermissions(client);
      const result = await this.triviaService.deleteGame(dto.gameId, sessionId);

      return {
        event: 'trivia.delete.response',
        data: { success: true, ...result },
      };
    } catch (error) {
      this.logger.error(
        `Failed to delete trivia game: ${getErrorMessage(error)}`,
      );
      return {
        event: 'trivia.delete.response',
        data: { success: false, error: getErrorMessage(error) },
      };
    }
  }

  // ─── Organizer: Start Game ──────────────────────────────────

  @SubscribeMessage('trivia.start')
  async handleStartGame(
    @MessageBody() dto: StartTriviaDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      this.assertOrganizerPermissions(client);
      const result = await this.triviaService.startGame(dto.gameId, sessionId);

      // Track activation time for the first question
      if (result.activeQuestion) {
        const now = Date.now();
        questionActivationTimes.set(result.activeQuestion.id, now);
        // Track game->question mapping for bulk cleanup
        const qIds = gameQuestionIds.get(dto.gameId) ?? new Set();
        qIds.add(result.activeQuestion.id);
        gameQuestionIds.set(dto.gameId, qIds);
      }

      // Broadcast game started to session
      const publicRoom = `session:${sessionId}`;
      this.server.to(publicRoom).emit('trivia.game.started', {
        game: result.game,
        activeQuestion: result.activeQuestion,
      });

      // Notify all competing teams
      for (const teamId of result.teamIds) {
        this.teamNotificationsService.notifyTriviaStarting(teamId, {
          gameId: result.game.id,
          gameName: result.game.name,
        });
      }

      return {
        event: 'trivia.start.response',
        data: { success: true, ...result },
      };
    } catch (error) {
      this.logger.error(
        `Failed to start trivia game: ${getErrorMessage(error)}`,
      );
      return {
        event: 'trivia.start.response',
        data: { success: false, error: getErrorMessage(error) },
      };
    }
  }

  // ─── Captain: Submit Answer ─────────────────────────────────

  @SubscribeMessage('trivia.answer.submit')
  async handleSubmitAnswer(
    @MessageBody() dto: SubmitTriviaAnswerDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      // Pass the gateway-tracked activation time for accurate speed bonus calculation
      const activationTimeMs = questionActivationTimes.get(dto.questionId);

      const result = await this.triviaService.submitAnswer(
        user.sub,
        dto.gameId,
        dto.questionId,
        dto.teamId,
        dto.selectedIndex,
        dto.idempotencyKey,
        activationTimeMs,
      );

      // Award gamification points if the answer is correct
      if (result.isCorrect) {
        void this.gamificationService
          .awardPoints(user.sub, sessionId, 'TRIVIA_CORRECT')
          .catch((err) =>
            this.logger.warn(
              `Failed to award TRIVIA_CORRECT points: ${err}`,
            ),
          );

        // Award speed bonus gamification points (service already computed eligibility)
        if (result.gotSpeedBonus) {
          void this.gamificationService
            .awardPoints(user.sub, sessionId, 'TRIVIA_SPEED_BONUS')
            .catch((err) =>
              this.logger.warn(
                `Failed to award TRIVIA_SPEED_BONUS points: ${err}`,
              ),
            );
        }
      }

      // Notify the team that their captain submitted
      this.server.to(`team:${dto.teamId}`).emit('trivia.answer.submitted', {
        questionId: dto.questionId,
        teamId: dto.teamId,
        submittedBy: user.sub,
        // Don't reveal correctness until organizer advances
      });

      return {
        event: 'trivia.answer.submit.response',
        data: { success: true, ...result },
      };
    } catch (error) {
      this.logger.error(
        `Failed to submit trivia answer: ${getErrorMessage(error)}`,
      );
      return {
        event: 'trivia.answer.submit.response',
        data: { success: false, error: getErrorMessage(error) },
      };
    }
  }

  // ─── Organizer: Advance Question ────────────────────────────

  @SubscribeMessage('trivia.advance')
  async handleAdvanceQuestion(
    @MessageBody() dto: AdvanceTriviaDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      this.assertOrganizerPermissions(client);
      const result = await this.triviaService.advanceQuestion(dto.gameId, sessionId);

      const publicRoom = `session:${sessionId}`;

      // Broadcast the revealed question with correct answer
      this.server.to(publicRoom).emit('trivia.question.revealed', {
        revealed: result.revealed,
        scores: result.scores,
      });

      // Broadcast updated scores
      this.server.to(publicRoom).emit('trivia.scores.updated', {
        gameId: dto.gameId,
        scores: result.scores,
      });

      // If there's a next question, broadcast it
      if (result.nextQuestion) {
        // Track activation time for the next question
        const now = Date.now();
        questionActivationTimes.set(result.nextQuestion.id, now);
        const qIds = gameQuestionIds.get(dto.gameId) ?? new Set();
        qIds.add(result.nextQuestion.id);
        gameQuestionIds.set(dto.gameId, qIds);

        this.server.to(publicRoom).emit('trivia.question.active', {
          gameId: dto.gameId,
          question: result.nextQuestion,
        });
      }

      // Clean up activation time for the revealed question
      questionActivationTimes.delete(result.revealed.questionId);

      return {
        event: 'trivia.advance.response',
        data: { success: true, ...result },
      };
    } catch (error) {
      this.logger.error(
        `Failed to advance trivia question: ${getErrorMessage(error)}`,
      );
      return {
        event: 'trivia.advance.response',
        data: { success: false, error: getErrorMessage(error) },
      };
    }
  }

  // ─── Organizer: End Game ────────────────────────────────────

  @SubscribeMessage('trivia.end')
  async handleEndGame(
    @MessageBody() dto: EndTriviaDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      this.assertOrganizerPermissions(client);
      const result = await this.triviaService.endGame(dto.gameId, sessionId);

      const publicRoom = `session:${sessionId}`;

      // Broadcast game completion with final scores
      this.server.to(publicRoom).emit('trivia.game.completed', {
        gameId: result.gameId,
        gameName: result.gameName,
        totalQuestions: result.totalQuestions,
        scores: result.scores,
      });

      // Award gamification points to all participating team members
      await this._awardTriviaCompletionPoints(
        result.scores,
        sessionId,
      );

      // Clean up all activation times for this game
      const qIds = gameQuestionIds.get(dto.gameId);
      if (qIds) {
        for (const qId of qIds) questionActivationTimes.delete(qId);
        gameQuestionIds.delete(dto.gameId);
      }

      return {
        event: 'trivia.end.response',
        data: { success: true, ...result },
      };
    } catch (error) {
      this.logger.error(
        `Failed to end trivia game: ${getErrorMessage(error)}`,
      );
      return {
        event: 'trivia.end.response',
        data: { success: false, error: getErrorMessage(error) },
      };
    }
  }

  // ─── Query: Game State (for reconnecting clients) ───────────

  @SubscribeMessage('trivia.state')
  async handleGetState(
    @MessageBody() data: { gameId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      getAuthenticatedUser(client); // Verify user is authenticated
      const state = await this.triviaService.getGameState(data.gameId, sessionId);
      return {
        event: 'trivia.state.response',
        data: { success: true, ...state },
      };
    } catch (error) {
      return {
        event: 'trivia.state.response',
        data: { success: false, error: getErrorMessage(error) },
      };
    }
  }

  // ─── Query: List Games ──────────────────────────────────────

  @SubscribeMessage('trivia.list')
  async handleListGames(
    @ConnectedSocket() client: AuthenticatedSocket,
    @MessageBody() data?: { status?: string },
  ) {
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const games = await this.triviaService.listGames(
        sessionId,
        data?.status,
      );
      return {
        event: 'trivia.list.response',
        data: { success: true, games },
      };
    } catch (error) {
      return {
        event: 'trivia.list.response',
        data: { success: false, error: getErrorMessage(error) },
      };
    }
  }

  // ─── Private Helpers ────────────────────────────────────────

  /**
   * Awards bonus gamification points based on final trivia placement.
   * Top team gets extra TRIVIA_CORRECT awards for all members.
   */
  private async _awardTriviaCompletionPoints(
    scores: Array<{
      rank: number;
      teamId: string;
      teamName: string;
      totalScore: number;
      correctCount: number;
    }>,
    sessionId: string,
  ) {
    // Award points to all members of participating teams
    for (const score of scores) {
      if (score.correctCount === 0) continue;

      try {
        const memberships = await this.prisma.teamMembership.findMany({
          where: { teamId: score.teamId },
          select: { userId: true },
        });

        for (const { userId } of memberships) {
          // Award TRIVIA_CORRECT for each correct answer the team got
          // (captain already got individual awards, but team members
          // also earn points proportional to team performance)
          void this.gamificationService
            .awardPoints(userId, sessionId, 'TRIVIA_CORRECT')
            .catch((err) =>
              this.logger.warn(
                `Failed to award trivia completion points to ${userId}: ${err}`,
              ),
            );
        }
      } catch (error) {
        this.logger.error(
          `Failed to award trivia points for team ${score.teamId}: ${getErrorMessage(error)}`,
        );
      }
    }
  }
}
