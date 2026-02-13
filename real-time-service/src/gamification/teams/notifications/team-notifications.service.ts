// src/gamification/teams/notifications/team-notifications.service.ts
import { Injectable, Logger } from '@nestjs/common';
import { Server } from 'socket.io';

/**
 * Pure Injectable service for broadcasting team-specific notifications.
 * Must receive the Server reference via setServer() from a gateway's afterInit().
 * All events are sent to `team:{teamId}` rooms.
 */
@Injectable()
export class TeamNotificationsService {
  private server: Server | null = null;
  private readonly logger = new Logger(TeamNotificationsService.name);

  /**
   * Called by a gateway's afterInit() to provide the shared Server instance.
   */
  setServer(server: Server) {
    this.server = server;
  }

  private emit(room: string, event: string, payload: Record<string, unknown>) {
    if (!this.server) {
      this.logger.warn(
        `Cannot emit ${event}: Server not yet initialized`,
      );
      return;
    }
    this.server.to(room).emit(event, payload);
  }

  notifyMemberJoined(
    teamId: string,
    member: { userId: string; firstName?: string; lastName?: string },
  ) {
    const room = `team:${teamId}`;
    this.emit(room, 'team.notification.member.joined', {
      teamId,
      member,
      timestamp: new Date().toISOString(),
    });
    this.logger.log(
      `Notified team ${teamId}: member ${member.userId} joined`,
    );
  }

  notifyMemberLeft(
    teamId: string,
    member: { userId: string; firstName?: string; lastName?: string },
  ) {
    const room = `team:${teamId}`;
    this.emit(room, 'team.notification.member.left', {
      teamId,
      member,
      timestamp: new Date().toISOString(),
    });
    this.logger.log(
      `Notified team ${teamId}: member ${member.userId} left`,
    );
  }

  notifyRankChanged(
    teamId: string,
    data: { previousRank: number; newRank: number; teamName: string },
  ) {
    const room = `team:${teamId}`;
    const direction =
      data.newRank < data.previousRank ? 'up' : 'down';
    this.emit(room, 'team.notification.rank.changed', {
      teamId,
      teamName: data.teamName,
      previousRank: data.previousRank,
      newRank: data.newRank,
      direction,
      timestamp: new Date().toISOString(),
    });
    this.logger.log(
      `Notified team ${teamId}: rank ${data.previousRank} -> ${data.newRank}`,
    );
  }

  notifyChallengeEvent(
    teamId: string,
    event: 'starting' | 'progress' | 'completed',
    data: Record<string, unknown>,
  ) {
    const room = `team:${teamId}`;
    this.emit(room, `team.notification.challenge.${event}`, {
      teamId,
      ...data,
      timestamp: new Date().toISOString(),
    });
  }

  notifyTriviaStarting(
    teamId: string,
    data: { gameId: string; gameName: string },
  ) {
    const room = `team:${teamId}`;
    this.emit(room, 'team.notification.trivia.starting', {
      teamId,
      ...data,
      timestamp: new Date().toISOString(),
    });
  }

  notifySynergyActive(
    teamId: string,
    data: { activeMembers: number; multiplier: number },
  ) {
    const room = `team:${teamId}`;
    this.emit(room, 'team.notification.synergy.active', {
      teamId,
      ...data,
      timestamp: new Date().toISOString(),
    });
  }
}
