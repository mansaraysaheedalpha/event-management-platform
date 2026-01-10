//src/comm/polls/polls.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { OnEvent } from '@nestjs/event-emitter';
import { Server } from 'socket.io';
import { ForbiddenException, Logger, NotFoundException } from '@nestjs/common';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { CreatePollDto } from './dto/create-poll.dto';
import { PollsService } from './polls.service';
import { ManagePollDto } from './dto/manage-polls.dto';
import { SubmitVoteDto } from './dto/submit-vote.dto';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { StartGiveawayDto } from './dto/start-giveaway.dto';
import { SessionSettingsService } from 'src/shared/services/session-settings.service';

// Admin/organizer permissions that can bypass polls_open check
const ADMIN_PERMISSIONS = [
  'content:manage',
  'poll:create',
  'poll:manage',
  'event:manage',
];

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class PollsGateway {
  private readonly logger = new Logger(PollsGateway.name);
  @WebSocketServer() server: Server;

  constructor(
    private readonly pollsService: PollsService,
    private readonly sessionSettingsService: SessionSettingsService,
  ) {}

  /**
   * Checks if user has admin/organizer permissions that bypass polls_open check.
   */
  private hasAdminPermissions(permissions: string[] | undefined): boolean {
    if (!permissions) return false;
    return permissions.some((p) => ADMIN_PERMISSIONS.includes(p));
  }

  /**
   * Validates that polls are active for the session.
   * - If polls_enabled is false: Block everyone (feature disabled)
   * - If polls_open is false: Block attendees, allow organizers (bypass)
   * - If both true: Allow everyone
   */
  private async validatePollsActive(
    sessionId: string,
    permissions?: string[],
  ): Promise<{ success: false; error: { message: string; statusCode: number } } | null> {
    const settings = await this.sessionSettingsService.getSessionSettings(sessionId);

    // If polls feature is completely disabled, block everyone
    if (!settings?.polls_enabled) {
      this.logger.warn(`[Polls] Polls are disabled for session ${sessionId}`);
      return {
        success: false,
        error: {
          message: 'Polls are disabled for this session.',
          statusCode: 403,
        },
      };
    }

    // If polls are closed, check if user has admin permissions to bypass
    if (!settings?.polls_open) {
      if (this.hasAdminPermissions(permissions)) {
        this.logger.log(
          `[Polls] Polls are closed for session ${sessionId}, but user has admin permissions - allowing bypass`,
        );
        return null; // Allow through
      }

      this.logger.warn(`[Polls] Polls are closed for session ${sessionId}`);
      return {
        success: false,
        error: {
          message: 'Polls are currently closed for this session.',
          statusCode: 403,
        },
      };
    }

    return null; // Polls are enabled and open
  }

  /**
   * Handles incoming request to create a new poll.
   * Checks user permissions, calls service to create poll,
   * and broadcasts the new poll to the session room.
   * @param dto - Data required to create the poll.
   * @param client - The connected authenticated socket client.
   * @returns success status and new poll ID or error info.
   */
  @SubscribeMessage('poll.create')
  async handleCreatePoll(
    @MessageBody() dto: CreatePollDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    const requiredPermission = 'poll:create';
    // We now safely check the permissions array.
    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to create a poll.',
      );
    }

    // Validate that polls are enabled AND open (organizers bypass open check)
    const pollsActiveError = await this.validatePollsActive(sessionId, user.permissions);
    if (pollsActiveError) return pollsActiveError;

    try {
      // We must `await` the promise from the service.
      const newPoll = await this.pollsService.createPoll(
        user.sub,
        sessionId,
        dto,
      );

      // We must check for null before using the result.
      if (!newPoll) {
        throw new Error('Poll creation returned an unexpected null result.');
      }

      const publicRoom = `session:${sessionId}`;
      const eventName = 'poll.opened';

      this.server.to(publicRoom).emit(eventName, newPoll);
      this.logger.log(
        `New poll ${newPoll.id} broadcasted to room ${publicRoom}`,
      );

      return { success: true, pollId: newPoll.id };
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(
        `Failed to create poll for user ${user.sub}:`,
        errorMessage,
      );
      return { success: false, error: errorMessage };
    }
  }

  /**
   * Handles incoming vote submission for a poll.
   * Submits the vote via service, then broadcasts updated poll results.
   * @param dto - Vote submission details.
   * @param client - The connected authenticated socket client.
   * @returns success status and poll ID or error info.
   */
  @SubscribeMessage('poll.vote.submit')
  async handleSubmitVote(
    @MessageBody() dto: SubmitVoteDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    // Validate that polls are enabled AND open (no bypass for voting - everyone must wait for polls to open)
    const pollsActiveError = await this.validatePollsActive(sessionId, user.permissions);
    if (pollsActiveError) return pollsActiveError;

    try {
      const updatedPollWithResults = await this.pollsService.submitVote(
        user.sub,
        user.email || '', // Pass email for user reference creation
        dto,
      );

      const publicRoom = `session:${sessionId}`;
      const eventName = 'poll.results.updated';

      this.server.to(publicRoom).emit(eventName, updatedPollWithResults);
      this.logger.log(
        `Updated poll results for ${dto.pollId} broadcasted to room ${publicRoom}`,
      );

      return { success: true, pollId: dto.pollId };
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(
        `Failed to submit vote for user ${user.sub}:`,
        errorMessage,
      );
      return { success: false, error: errorMessage };
    }
  }

  /**
   * Handles requests to manage a poll (e.g., closing a poll).
   * Checks user permissions, performs management action via service,
   * then broadcasts final poll results to the session room.
   * @param dto - Poll management instructions.
   * @param client - The connected authenticated socket client.
   * @returns success status, poll ID, and final status or error info.
   */
  @SubscribeMessage('poll.manage')
  async handleManagePoll(
    @MessageBody() dto: ManagePollDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    const requiredPermission = 'poll:manage';
    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to manage polls.',
      );
    }

    try {
      const finalPollResults = await this.pollsService.managePoll(
        user.sub,
        dto,
      );

      if (!finalPollResults) {
        throw new NotFoundException(
          'Poll to manage was not found or already in the desired state.',
        );
      }

      const publicRoom = `session:${sessionId}`;
      const eventName = 'poll.closed';

      this.server.to(publicRoom).emit(eventName, finalPollResults);
      this.logger.log(
        `Final poll results for ${dto.pollId} broadcasted to room ${publicRoom}`,
      );

      return { success: true, pollId: dto.pollId, finalStatus: 'closed' };
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(
        `Failed to manage poll for user ${user.sub}:`,
        errorMessage,
      );
      return { success: false, error: errorMessage };
    }
  }

  /**
   * Handles an admin starting a giveaway for a poll.
   * Broadcasts to all users and sends a personal notification to the winner.
   */
  @SubscribeMessage('poll.giveaway.start')
  async handleStartGiveaway(
    @MessageBody() dto: StartGiveawayDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    const requiredPermission = 'poll:manage'; // Same permission as closing a poll
    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to manage giveaways.',
      );
    }

    try {
      const giveawayResult = await this.pollsService.selectGiveawayWinner(
        dto,
        user.sub,
      );

      if (giveawayResult && giveawayResult.success && giveawayResult.winner) {
        const publicRoom = `session:${sessionId}`;
        const winner = giveawayResult.winner;

        // 1. Broadcast to all users (without email for privacy)
        const publicPayload = {
          ...giveawayResult,
          winner: {
            id: winner.id,
            name: winner.name,
            firstName: winner.firstName,
            lastName: winner.lastName,
            optionText: winner.optionText,
            // Email is intentionally excluded from public broadcast
          },
        };
        this.server.to(publicRoom).emit('poll.giveaway.winner', publicPayload);
        this.logger.log(
          `Broadcasted giveaway winner for poll ${dto.pollId} to room ${publicRoom}`,
        );

        // 2. Send a private notification to the winner
        const winnerRoom = `user:${winner.id}`;
        this.server.to(winnerRoom).emit('poll.giveaway.you-won', {
          pollId: dto.pollId,
          giveawayWinnerId: giveawayResult.giveawayWinnerId,
          prize: giveawayResult.prize,
          message: 'Congratulations! You won the giveaway! 🎉',
        });
        this.logger.log(
          `Sent private winner notification to user ${winner.id}`,
        );
      }

      return {
        success: giveawayResult?.success ?? false,
        winner: giveawayResult?.winner,
        totalEligibleVoters: giveawayResult?.totalEligibleVoters,
        giveawayWinnerId: giveawayResult?.giveawayWinnerId,
      };
    } catch (error) {
      this.logger.error(
        `Failed to start giveaway for admin ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  // ============================================================
  // QUIZ GIVEAWAY HANDLERS
  // ============================================================

  /**
   * Handles request to get quiz leaderboard.
   */
  @SubscribeMessage('quiz.leaderboard.get')
  async handleGetQuizLeaderboard(
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const leaderboard = await this.pollsService.getQuizLeaderboard(
        sessionId,
        user.sub,
      );
      return { success: true, ...leaderboard };
    } catch (error) {
      this.logger.error('Failed to get quiz leaderboard', getErrorMessage(error));
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Handles admin running a quiz giveaway.
   * Broadcasts results to all users and sends private notifications to winners.
   */
  @SubscribeMessage('quiz.giveaway.start')
  async handleStartQuizGiveaway(
    @MessageBody() dto: { idempotencyKey: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    const requiredPermission = 'poll:manage';
    if (!user.permissions?.includes(requiredPermission)) {
      throw new ForbiddenException(
        'You do not have permission to run quiz giveaways.',
      );
    }

    try {
      const giveawayResult = await this.pollsService.runQuizGiveaway(
        sessionId,
        user.sub,
        dto.idempotencyKey,
      );

      if (giveawayResult.success) {
        const publicRoom = `session:${sessionId}`;

        // 1. Broadcast results to all users
        this.server.to(publicRoom).emit('quiz.giveaway.results', {
          sessionId,
          stats: giveawayResult.quizStats,
          totalWinners: giveawayResult.totalWinners,
          prize: giveawayResult.prize,
        });
        this.logger.log(
          `Broadcasted quiz giveaway results to room ${publicRoom}`,
        );

        // 2. Send private notifications to each winner
        for (const winner of giveawayResult.winners) {
          const winnerRoom = `user:${winner.id}`;
          this.server.to(winnerRoom).emit('quiz.giveaway.you-won', {
            sessionId,
            score: winner.score,
            totalQuestions: winner.totalQuestions,
            percentage: winner.percentage,
            prize: giveawayResult.prize,
            message: `Congratulations! You scored ${winner.score}/${winner.totalQuestions} and won! 🏆`,
          });
        }
        this.logger.log(
          `Sent private winner notifications to ${giveawayResult.winners.length} users`,
        );
      }

      return {
        success: true,
        totalWinners: giveawayResult.totalWinners,
        quizStats: giveawayResult.quizStats,
      };
    } catch (error) {
      this.logger.error(
        `Failed to run quiz giveaway for admin ${user.sub}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Handles polls status change events from Redis (when organizer toggles pollsOpen).
   * Broadcasts the status change to all clients in the session room.
   * Also clears the session settings cache so the new status is used immediately.
   */
  @OnEvent('platform.sessions.polls.v1')
  async handlePollsStatusChange(payload: {
    sessionId: string;
    pollsOpen: boolean;
    eventId: string;
  }) {
    const { sessionId, pollsOpen } = payload;

    // Clear the cache so the new status is fetched on next request
    this.sessionSettingsService.clearCache(sessionId);

    // Broadcast to all clients in the session room
    const room = `session:${sessionId}`;
    this.server.to(room).emit('polls.status.changed', {
      sessionId,
      isOpen: pollsOpen,
      message: pollsOpen
        ? 'Polls are now open! You can create polls and vote.'
        : 'Polls are now closed.',
    });

    this.logger.log(
      `[Polls] Status changed for session ${sessionId}: pollsOpen=${pollsOpen}`,
    );
  }
}
