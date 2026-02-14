// src/gamification/teams/trivia/trivia.service.ts
import {
  ConflictException,
  ForbiddenException,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { CreateTriviaGameDto } from './dto/create-trivia-game.dto';

@Injectable()
export class TriviaService {
  private readonly logger = new Logger(TriviaService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
  ) {}

  // ─── Game Lifecycle ─────────────────────────────────────────

  /**
   * Creates a trivia game in DRAFT status with all questions.
   */
  async createGame(
    creatorId: string,
    sessionId: string,
    dto: CreateTriviaGameDto,
  ) {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException('This trivia game has already been created.');
    }

    const game = await this.prisma.triviaGame.create({
      data: {
        sessionId,
        name: dto.name,
        timePerQuestion: dto.timePerQuestion ?? 30,
        pointsCorrect: dto.pointsCorrect ?? 10,
        pointsSpeedBonus: dto.pointsSpeedBonus ?? 5,
        createdById: creatorId,
        questions: {
          create: dto.questions.map((q, index) => ({
            questionText: q.questionText,
            options: q.options,
            correctIndex: q.correctIndex,
            orderIndex: index,
          })),
        },
      },
      include: {
        questions: { orderBy: { orderIndex: 'asc' } },
      },
    });

    this.logger.log(
      `Trivia game ${game.id} (${game.name}) created with ${game.questions.length} questions for session ${sessionId}`,
    );
    return game;
  }

  /**
   * Starts a DRAFT game: transitions to ACTIVE and activates the first question.
   * Returns the game with the active question (correctIndex stripped for broadcast).
   */
  async startGame(gameId: string, sessionId: string) {
    const game = await this.prisma.triviaGame.findUnique({
      where: { id: gameId },
      include: {
        questions: { orderBy: { orderIndex: 'asc' } },
      },
    });

    if (!game) throw new NotFoundException(`Trivia game ${gameId} not found.`);
    if (game.sessionId !== sessionId) {
      throw new ForbiddenException('Game does not belong to this session.');
    }
    if (game.status !== 'DRAFT') {
      throw new ConflictException(
        `Game is ${game.status}, not DRAFT.`,
      );
    }
    if (game.questions.length === 0) {
      throw new ConflictException('Game has no questions.');
    }

    // Initialize team scores for all teams in the session
    const teams = await this.prisma.team.findMany({
      where: { sessionId: game.sessionId },
      select: { id: true },
    });

    await this.prisma.$transaction(async (tx) => {
      // Transition game to ACTIVE
      await tx.triviaGame.update({
        where: { id: gameId },
        data: { status: 'ACTIVE' },
      });

      // Activate the first question
      await tx.triviaQuestion.update({
        where: { id: game.questions[0].id },
        data: { status: 'ACTIVE' },
      });

      // Create team score entries
      if (teams.length > 0) {
        await tx.triviaTeamScore.createMany({
          data: teams.map((t) => ({
            gameId,
            teamId: t.id,
            totalScore: 0,
            correctCount: 0,
            speedBonuses: 0,
          })),
          skipDuplicates: true,
        });
      }
    });

    const firstQuestion = game.questions[0];

    this.logger.log(
      `Trivia game ${gameId} started. First question: ${firstQuestion.id}. ${teams.length} teams competing.`,
    );

    return {
      game: {
        id: game.id,
        name: game.name,
        sessionId: game.sessionId,
        timePerQuestion: game.timePerQuestion,
        pointsCorrect: game.pointsCorrect,
        pointsSpeedBonus: game.pointsSpeedBonus,
        totalQuestions: game.questions.length,
      },
      activeQuestion: {
        id: firstQuestion.id,
        questionText: firstQuestion.questionText,
        options: firstQuestion.options,
        orderIndex: firstQuestion.orderIndex,
        totalQuestions: game.questions.length,
      },
      teamIds: teams.map((t) => t.id),
    };
  }

  // ─── Answer Submission ──────────────────────────────────────

  /**
   * Submits an answer for a team. Only the team captain can submit.
   * Captain = Team.creatorId.
   */
  async submitAnswer(
    userId: string,
    gameId: string,
    questionId: string,
    teamId: string,
    selectedIndex: number,
    idempotencyKey: string,
    /** Activation timestamp (ms since epoch) from the gateway's in-memory map */
    activationTimeMs?: number,
  ) {
    const canProceed =
      await this.idempotencyService.checkAndSet(idempotencyKey);
    if (!canProceed) {
      throw new ConflictException('This answer has already been submitted.');
    }

    // Verify captain
    const team = await this.prisma.team.findUnique({
      where: { id: teamId },
      select: { creatorId: true, sessionId: true },
    });
    if (!team) throw new NotFoundException(`Team ${teamId} not found.`);
    if (team.creatorId !== userId) {
      throw new ForbiddenException(
        'Only the team captain can submit trivia answers.',
      );
    }

    // Verify the question is ACTIVE and belongs to this game
    const question = await this.prisma.triviaQuestion.findFirst({
      where: { id: questionId, gameId, status: 'ACTIVE' },
      include: {
        game: { select: { sessionId: true, timePerQuestion: true, pointsCorrect: true, pointsSpeedBonus: true } },
      },
    });
    if (!question) {
      throw new ConflictException(
        'This question is not currently active or does not belong to this game.',
      );
    }

    // Cross-session validation: team must belong to the same session as the game
    if (team.sessionId !== question.game.sessionId) {
      throw new ForbiddenException(
        'Team does not belong to the same session as this game.',
      );
    }

    // Validate selectedIndex is within the question's options
    if (selectedIndex >= question.options.length) {
      throw new ConflictException(
        `Invalid answer index ${selectedIndex}. This question has ${question.options.length} options.`,
      );
    }

    // Calculate response time using gateway-provided activation time (accurate)
    // Falls back to 0 if unavailable (won't award speed bonus without accurate time)
    const responseTimeMs = activationTimeMs
      ? Math.max(0, Date.now() - activationTimeMs)
      : 0;

    const isCorrect = selectedIndex === question.correctIndex;

    // Atomic: create answer with conflict handling for the unique constraint.
    // This prevents the race condition where two concurrent requests both pass
    // the findUnique check and then both try to create.
    let answer;
    try {
      answer = await this.prisma.triviaAnswer.create({
        data: {
          questionId,
          teamId,
          submittedById: userId,
          selectedIndex,
          isCorrect,
          responseTimeMs,
        },
      });
    } catch (err: any) {
      // P2002 = Unique constraint violation (team already answered)
      if (err?.code === 'P2002') {
        throw new ConflictException(
          'Your team has already submitted an answer for this question.',
        );
      }
      throw err;
    }

    // If correct, update team score (upsert is already atomic)
    if (isCorrect) {
      const timePerQuestionMs = question.game.timePerQuestion * 1000;
      // Speed bonus: awarded if answered in less than half the allowed time
      const earnedSpeedBonus =
        activationTimeMs && responseTimeMs < timePerQuestionMs / 2
          ? question.game.pointsSpeedBonus
          : 0;

      await this.prisma.triviaTeamScore.upsert({
        where: { gameId_teamId: { gameId, teamId } },
        update: {
          totalScore: {
            increment: question.game.pointsCorrect + earnedSpeedBonus,
          },
          correctCount: { increment: 1 },
          speedBonuses: { increment: earnedSpeedBonus > 0 ? 1 : 0 },
        },
        create: {
          gameId,
          teamId,
          totalScore: question.game.pointsCorrect + earnedSpeedBonus,
          correctCount: 1,
          speedBonuses: earnedSpeedBonus > 0 ? 1 : 0,
        },
      });
    }

    this.logger.log(
      `Team ${teamId} submitted answer for question ${questionId}: index=${selectedIndex}, correct=${isCorrect}, responseTime=${responseTimeMs}ms`,
    );

    // Determine if speed bonus was earned (for gateway to award gamification points)
    const timePerQuestionMs = question.game.timePerQuestion * 1000;
    const gotSpeedBonus =
      isCorrect && activationTimeMs != null && responseTimeMs < timePerQuestionMs / 2;

    return {
      answerId: answer.id,
      teamId,
      isCorrect,
      responseTimeMs,
      gotSpeedBonus,
      // Don't reveal correctIndex — that happens on advance/reveal
    };
  }

  // ─── Question Advancement ──────────────────────────────────

  /**
   * Advances to the next question: reveals the current question's answer,
   * then activates the next question. If no more questions, returns null
   * to signal game completion.
   */
  async advanceQuestion(gameId: string, sessionId: string) {
    const game = await this.prisma.triviaGame.findUnique({
      where: { id: gameId },
      include: {
        questions: { orderBy: { orderIndex: 'asc' } },
      },
    });

    if (!game) throw new NotFoundException(`Trivia game ${gameId} not found.`);
    if (game.sessionId !== sessionId) {
      throw new ForbiddenException('Game does not belong to this session.');
    }
    if (game.status !== 'ACTIVE') {
      throw new ConflictException(`Game is ${game.status}, not ACTIVE.`);
    }

    // Find the current active question
    const activeQuestion = game.questions.find((q) => q.status === 'ACTIVE');
    if (!activeQuestion) {
      throw new ConflictException('No active question found.');
    }

    // Get answers for the active question (for reveal)
    const answers = await this.prisma.triviaAnswer.findMany({
      where: { questionId: activeQuestion.id },
      include: {
        team: { select: { id: true, name: true } },
      },
    });

    // Reveal the current question
    await this.prisma.triviaQuestion.update({
      where: { id: activeQuestion.id },
      data: { status: 'REVEALED' },
    });

    // Get current scores
    const scores = await this._getTeamScores(gameId);

    // Find the next question
    const nextQuestion = game.questions.find(
      (q) => q.orderIndex > activeQuestion.orderIndex && q.status === 'PENDING',
    );

    if (nextQuestion) {
      // Activate next question
      await this.prisma.triviaQuestion.update({
        where: { id: nextQuestion.id },
        data: { status: 'ACTIVE' },
      });

      this.logger.log(
        `Trivia game ${gameId}: revealed Q${activeQuestion.orderIndex}, activated Q${nextQuestion.orderIndex}`,
      );

      return {
        revealed: {
          questionId: activeQuestion.id,
          questionText: activeQuestion.questionText,
          options: activeQuestion.options,
          correctIndex: activeQuestion.correctIndex,
          orderIndex: activeQuestion.orderIndex,
          answers: answers.map((a) => ({
            teamId: a.teamId,
            teamName: a.team.name,
            selectedIndex: a.selectedIndex,
            isCorrect: a.isCorrect,
            responseTimeMs: a.responseTimeMs,
          })),
        },
        scores,
        nextQuestion: {
          id: nextQuestion.id,
          questionText: nextQuestion.questionText,
          options: nextQuestion.options,
          orderIndex: nextQuestion.orderIndex,
          totalQuestions: game.questions.length,
        },
        isLastQuestion: false,
      };
    }

    // No more questions — game should be completed
    this.logger.log(
      `Trivia game ${gameId}: revealed final question Q${activeQuestion.orderIndex}. Ready for completion.`,
    );

    return {
      revealed: {
        questionId: activeQuestion.id,
        questionText: activeQuestion.questionText,
        options: activeQuestion.options,
        correctIndex: activeQuestion.correctIndex,
        orderIndex: activeQuestion.orderIndex,
        answers: answers.map((a) => ({
          teamId: a.teamId,
          teamName: a.team.name,
          selectedIndex: a.selectedIndex,
          isCorrect: a.isCorrect,
          responseTimeMs: a.responseTimeMs,
        })),
      },
      scores,
      nextQuestion: null,
      isLastQuestion: true,
    };
  }

  // ─── Game Completion ────────────────────────────────────────

  /**
   * Ends the trivia game: transitions to COMPLETED and returns final scores
   * ranked by total score.
   */
  async endGame(gameId: string, sessionId: string) {
    const game = await this.prisma.triviaGame.findUnique({
      where: { id: gameId },
      include: { questions: true },
    });

    if (!game) throw new NotFoundException(`Trivia game ${gameId} not found.`);
    if (game.sessionId !== sessionId) {
      throw new ForbiddenException('Game does not belong to this session.');
    }
    if (game.status !== 'ACTIVE') {
      throw new ConflictException(`Game is ${game.status}, not ACTIVE.`);
    }

    // Mark any remaining ACTIVE/PENDING questions as REVEALED
    await this.prisma.triviaQuestion.updateMany({
      where: {
        gameId,
        status: { in: ['ACTIVE', 'PENDING'] },
      },
      data: { status: 'REVEALED' },
    });

    // Transition game to COMPLETED
    await this.prisma.triviaGame.update({
      where: { id: gameId },
      data: { status: 'COMPLETED' },
    });

    // Get final scores
    const scores = await this._getTeamScores(gameId);

    this.logger.log(
      `Trivia game ${gameId} completed. Rankings: ${scores.map((s, i) => `#${i + 1} ${s.teamName} (${s.totalScore})`).join(', ')}`,
    );

    return {
      gameId: game.id,
      gameName: game.name,
      sessionId: game.sessionId,
      totalQuestions: game.questions.length,
      scores,
    };
  }

  // ─── Delete Game ──────────────────────────────────────────

  /**
   * Deletes a DRAFT trivia game and all its questions.
   * Only DRAFT games can be deleted (not ACTIVE or COMPLETED).
   */
  async deleteGame(gameId: string, sessionId: string) {
    const game = await this.prisma.triviaGame.findUnique({
      where: { id: gameId },
    });

    if (!game) throw new NotFoundException(`Trivia game ${gameId} not found.`);
    if (game.sessionId !== sessionId) {
      throw new ForbiddenException('Game does not belong to this session.');
    }
    if (game.status !== 'DRAFT') {
      throw new ConflictException(
        `Only DRAFT games can be deleted. This game is ${game.status}.`,
      );
    }

    // Delete questions first (cascade), then the game
    await this.prisma.$transaction([
      this.prisma.triviaQuestion.deleteMany({ where: { gameId } }),
      this.prisma.triviaGame.delete({ where: { id: gameId } }),
    ]);

    this.logger.log(`Trivia game ${gameId} (${game.name}) deleted.`);
    return { gameId, name: game.name };
  }

  // ─── Queries ────────────────────────────────────────────────

  /**
   * Lists all trivia games for a session.
   */
  private static readonly VALID_GAME_STATUSES = ['DRAFT', 'ACTIVE', 'COMPLETED'];

  async listGames(sessionId: string, status?: string) {
    const where: any = { sessionId };
    if (status) {
      if (!TriviaService.VALID_GAME_STATUSES.includes(status)) {
        throw new ConflictException(
          `Invalid status "${status}". Must be one of: ${TriviaService.VALID_GAME_STATUSES.join(', ')}`,
        );
      }
      where.status = status;
    }

    return this.prisma.triviaGame.findMany({
      where,
      include: {
        questions: {
          orderBy: { orderIndex: 'asc' },
          select: {
            id: true,
            questionText: true,
            options: true,
            orderIndex: true,
            status: true,
            // Intentionally omit correctIndex for non-revealed questions
          },
        },
        teamScores: {
          include: { team: { select: { id: true, name: true } } },
          orderBy: { totalScore: 'desc' },
        },
      },
      orderBy: { createdAt: 'desc' },
    });
  }

  /**
   * Gets current state of an active game (for reconnecting clients).
   */
  async getGameState(gameId: string, sessionId: string) {
    const game = await this.prisma.triviaGame.findUnique({
      where: { id: gameId },
      include: {
        questions: { orderBy: { orderIndex: 'asc' } },
        teamScores: {
          include: { team: { select: { id: true, name: true } } },
          orderBy: { totalScore: 'desc' },
        },
      },
    });

    if (!game) throw new NotFoundException(`Trivia game ${gameId} not found.`);
    if (game.sessionId !== sessionId) {
      throw new ForbiddenException('Game does not belong to this session.');
    }

    const activeQuestion = game.questions.find((q) => q.status === 'ACTIVE');

    return {
      game: {
        id: game.id,
        name: game.name,
        status: game.status,
        timePerQuestion: game.timePerQuestion,
        totalQuestions: game.questions.length,
      },
      activeQuestion: activeQuestion
        ? {
            id: activeQuestion.id,
            questionText: activeQuestion.questionText,
            options: activeQuestion.options,
            orderIndex: activeQuestion.orderIndex,
            totalQuestions: game.questions.length,
          }
        : null,
      revealedQuestions: game.questions
        .filter((q) => q.status === 'REVEALED')
        .map((q) => ({
          id: q.id,
          questionText: q.questionText,
          options: q.options,
          correctIndex: q.correctIndex,
          orderIndex: q.orderIndex,
        })),
      scores: game.teamScores.map((s, i) => ({
        rank: i + 1,
        teamId: s.teamId,
        teamName: s.team.name,
        totalScore: s.totalScore,
        correctCount: s.correctCount,
        speedBonuses: s.speedBonuses,
      })),
    };
  }

  // ─── Private Helpers ────────────────────────────────────────

  private async _getTeamScores(gameId: string) {
    const scores = await this.prisma.triviaTeamScore.findMany({
      where: { gameId },
      include: { team: { select: { id: true, name: true } } },
      orderBy: { totalScore: 'desc' },
    });

    return scores.map((s, i) => ({
      rank: i + 1,
      teamId: s.teamId,
      teamName: s.team.name,
      totalScore: s.totalScore,
      correctCount: s.correctCount,
      speedBonuses: s.speedBonuses,
    }));
  }

}
