// src/gamification/teams/challenges/challenges.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger, OnModuleDestroy } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { ForbiddenException } from '@nestjs/common';
import { ChallengesService } from './challenges.service';
import { CreateChallengeDto } from './dto/create-challenge.dto';
import { StartChallengeDto } from './dto/start-challenge.dto';
import { CancelChallengeDto } from './dto/cancel-challenge.dto';
import { GamificationService } from '../../gamification.service';
import { TeamNotificationsService } from '../notifications/team-notifications.service';
import { PrismaService } from 'src/prisma.service';
import { PointReason } from '@prisma/client';

// Debounce progress broadcasts (2 seconds per challenge)
const PROGRESS_DEBOUNCE_MS = 2000;

// Permissions that allow challenge management (organizers/admins)
const CHALLENGE_ADMIN_PERMISSIONS = [
  'event:manage',
  'content:manage',
  'gamification:manage',
];

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class ChallengesGateway implements OnModuleDestroy {
  private readonly logger = new Logger(ChallengesGateway.name);
  @WebSocketServer() server: Server;

  // Per-challenge debounce timers for progress broadcasts
  private progressDebounceTimers = new Map<string, NodeJS.Timeout>();

  constructor(
    private readonly challengesService: ChallengesService,
    private readonly gamificationService: GamificationService,
    private readonly teamNotificationsService: TeamNotificationsService,
    private readonly prisma: PrismaService,
  ) {}

  // ─── Authorization ──────────────────────────────────────────

  private assertOrganizerPermissions(client: AuthenticatedSocket) {
    const user = getAuthenticatedUser(client);
    const hasPermission = user.permissions?.some((p) =>
      CHALLENGE_ADMIN_PERMISSIONS.includes(p),
    );
    if (!hasPermission) {
      throw new ForbiddenException(
        'You do not have permission to manage challenges.',
      );
    }
  }

  // ─── Organizer Actions ────────────────────────────────────────

  @SubscribeMessage('challenge.templates')
  handleGetTemplates() {
    const templates = this.challengesService.getTemplates();
    return {
      event: 'challenge.templates.response',
      data: { success: true, templates },
    };
  }

  @SubscribeMessage('challenge.create')
  async handleCreateChallenge(
    @MessageBody() dto: CreateChallengeDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      this.assertOrganizerPermissions(client);
      const challenge = await this.challengesService.createChallenge(
        user.sub,
        sessionId,
        dto,
      );

      // Broadcast to session
      const publicRoom = `session:${sessionId}`;
      this.server.to(publicRoom).emit('challenge.created', challenge);

      return {
        event: 'challenge.create.response',
        data: { success: true, challenge },
      };
    } catch (error) {
      this.logger.error(
        `Failed to create challenge: ${getErrorMessage(error)}`,
      );
      return {
        event: 'challenge.create.response',
        data: { success: false, error: getErrorMessage(error) },
      };
    }
  }

  @SubscribeMessage('challenge.start')
  async handleStartChallenge(
    @MessageBody() dto: StartChallengeDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      this.assertOrganizerPermissions(client);
      const challenge = await this.challengesService.startChallenge(
        dto.challengeId,
      );

      // Broadcast to session
      const publicRoom = `session:${sessionId}`;
      this.server.to(publicRoom).emit('challenge.started', {
        challengeId: challenge.id,
        name: challenge.name,
        type: challenge.type,
        durationMinutes: challenge.durationMinutes,
        startedAt: challenge.startedAt,
        endedAt: challenge.endedAt,
      });

      // Notify all teams
      const teams = await this.challengesService.getActiveProgress(
        dto.challengeId,
      );
      for (const team of teams.teams) {
        this.teamNotificationsService.notifyChallengeEvent(
          team.teamId,
          'starting',
          {
            challengeId: challenge.id,
            challengeName: challenge.name,
            durationMinutes: challenge.durationMinutes,
          },
        );
      }

      return {
        event: 'challenge.start.response',
        data: { success: true, challenge },
      };
    } catch (error) {
      this.logger.error(
        `Failed to start challenge: ${getErrorMessage(error)}`,
      );
      return {
        event: 'challenge.start.response',
        data: { success: false, error: getErrorMessage(error) },
      };
    }
  }

  @SubscribeMessage('challenge.cancel')
  async handleCancelChallenge(
    @MessageBody() dto: CancelChallengeDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      this.assertOrganizerPermissions(client);
      const challenge = await this.challengesService.cancelChallenge(
        dto.challengeId,
      );

      const publicRoom = `session:${sessionId}`;
      this.server.to(publicRoom).emit('challenge.cancelled', {
        challengeId: challenge.id,
        name: challenge.name,
      });

      return {
        event: 'challenge.cancel.response',
        data: { success: true },
      };
    } catch (error) {
      this.logger.error(
        `Failed to cancel challenge: ${getErrorMessage(error)}`,
      );
      return {
        event: 'challenge.cancel.response',
        data: { success: false, error: getErrorMessage(error) },
      };
    }
  }

  @SubscribeMessage('challenge.list')
  async handleListChallenges(
    @ConnectedSocket() client: AuthenticatedSocket,
    @MessageBody() data?: { status?: string },
  ) {
    const { sessionId } = client.handshake.query as { sessionId: string };

    try {
      const challenges = await this.challengesService.listChallenges(
        sessionId,
        data?.status,
      );
      return {
        event: 'challenge.list.response',
        data: { success: true, challenges },
      };
    } catch (error) {
      this.logger.error(
        `Failed to list challenges: ${getErrorMessage(error)}`,
      );
      return {
        event: 'challenge.list.response',
        data: { success: false, error: getErrorMessage(error) },
      };
    }
  }

  @SubscribeMessage('challenge.progress')
  async handleGetProgress(
    @MessageBody() data: { challengeId: string },
  ) {
    try {
      const progress = await this.challengesService.getActiveProgress(
        data.challengeId,
      );
      return {
        event: 'challenge.progress.response',
        data: { success: true, ...progress },
      };
    } catch (error) {
      return {
        event: 'challenge.progress.response',
        data: { success: false, error: getErrorMessage(error) },
      };
    }
  }

  // ─── Action Tracking (from GamificationService event) ─────────

  /**
   * Listens for gamification actions emitted by GamificationService.awardPoints().
   * Checks active challenges and increments progress, then debounced-broadcasts.
   */
  @OnEvent('gamification.action')
  async handleGamificationAction(payload: {
    userId: string;
    sessionId: string;
    reason: PointReason;
    teamId: string | null;
  }) {
    if (!payload.teamId) return;

    try {
      const progressUpdates = await this.challengesService.trackAction(
        payload.sessionId,
        payload.teamId,
        payload.reason,
      );

      // Debounced broadcast for each challenge that had progress
      for (const update of progressUpdates) {
        this._debouncedProgressBroadcast(
          payload.sessionId,
          update.challengeId,
        );
      }
    } catch (error) {
      this.logger.warn(
        `Challenge tracking failed: ${getErrorMessage(error)}`,
      );
    }
  }

  // ─── Challenge Completion (called by scheduler) ──────────────

  /**
   * Completes a challenge, awards points to winning teams, and broadcasts results.
   */
  async completeAndBroadcast(sessionId: string, challengeId: string) {
    try {
      const result =
        await this.challengesService.completeChallenge(challengeId);

      // null means another process already completed this challenge
      if (!result) return;

      // Award points to top 3 teams
      const rewardReasons: PointReason[] = [
        'CHALLENGE_WON_FIRST',
        'CHALLENGE_WON_SECOND',
        'CHALLENGE_WON_THIRD',
      ];

      for (
        let i = 0;
        i < Math.min(3, result.rankings.length);
        i++
      ) {
        const { teamId } = result.rankings[i];
        // Award points to all members of this team
        await this._awardTeamPoints(
          teamId,
          sessionId,
          rewardReasons[i],
        );

        // Also award CHALLENGE_COMPLETED to all team members
        await this._awardTeamPoints(
          teamId,
          sessionId,
          'CHALLENGE_COMPLETED',
        );

        // Notify the team
        this.teamNotificationsService.notifyChallengeEvent(
          teamId,
          'completed',
          {
            challengeId,
            challengeName: result.challenge.name,
            rank: i + 1,
            score: result.rankings[i].score,
          },
        );
      }

      // Notify remaining teams about completion
      for (let i = 3; i < result.rankings.length; i++) {
        const { teamId } = result.rankings[i];
        await this._awardTeamPoints(
          teamId,
          sessionId,
          'CHALLENGE_COMPLETED',
        );
        this.teamNotificationsService.notifyChallengeEvent(
          teamId,
          'completed',
          {
            challengeId,
            challengeName: result.challenge.name,
            rank: i + 1,
            score: result.rankings[i].score,
          },
        );
      }

      // Broadcast completion to session
      const publicRoom = `session:${sessionId}`;
      this.server.to(publicRoom).emit('challenge.completed', {
        challengeId,
        name: result.challenge.name,
        rankings: result.rankings,
      });

      this.logger.log(
        `Challenge ${challengeId} completed and rewards distributed.`,
      );
    } catch (error) {
      this.logger.error(
        `Failed to complete challenge ${challengeId}: ${getErrorMessage(error)}`,
      );
    }
  }

  // ─── Private Helpers ─────────────────────────────────────────

  private _debouncedProgressBroadcast(
    sessionId: string,
    challengeId: string,
  ) {
    const key = challengeId;
    const existing = this.progressDebounceTimers.get(key);
    if (existing) clearTimeout(existing);

    const timer = setTimeout(async () => {
      this.progressDebounceTimers.delete(key);
      try {
        const progress =
          await this.challengesService.getActiveProgress(challengeId);
        const publicRoom = `session:${sessionId}`;
        this.server
          .to(publicRoom)
          .emit('challenge.progress.updated', progress);
      } catch (error) {
        this.logger.warn(
          `Failed to broadcast challenge progress: ${getErrorMessage(error)}`,
        );
      }
    }, PROGRESS_DEBOUNCE_MS);

    this.progressDebounceTimers.set(key, timer);
  }

  /**
   * Awards points to all members of a team for a given reason.
   */
  private async _awardTeamPoints(
    teamId: string,
    sessionId: string,
    reason: PointReason,
  ) {
    try {
      const memberships = await this.prisma.teamMembership.findMany({
        where: { teamId },
        select: { userId: true },
      });

      for (const { userId } of memberships) {
        void this.gamificationService
          .awardPoints(userId, sessionId, reason)
          .catch((err) =>
            this.logger.warn(
              `Failed to award ${reason} to user ${userId}: ${err?.message || err}`,
            ),
          );
      }
    } catch (error) {
      this.logger.error(
        `Failed to award team points for team ${teamId}: ${getErrorMessage(error)}`,
      );
    }
  }

  onModuleDestroy() {
    this.progressDebounceTimers.forEach((timer) => clearTimeout(timer));
    this.progressDebounceTimers.clear();
  }
}
