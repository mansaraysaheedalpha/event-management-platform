// src/networking/retention/retention.service.ts
import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from 'src/prisma.service';
import { KafkaService } from 'src/shared/kafka/kafka.service';
import { ConnectionsService } from '../connections/connections.service';
import { FollowUpService } from '../follow-up/follow-up.service';

// Kafka topics for retention events
export const RETENTION_KAFKA_TOPICS = {
  FOLLOW_UP_REMINDER: 'networking.follow-up-reminder.v1',
  STALE_CONNECTION_NUDGE: 'networking.stale-connection-nudge.v1',
  WEEKLY_NETWORK_DIGEST: 'networking.weekly-digest.v1',
  MILESTONE_NOTIFICATION: 'networking.milestone.v1',
};

// Retention configuration
interface RetentionConfig {
  followUpReminderDays: number;
  staleConnectionDays: number;
  digestEnabled: boolean;
  maxRemindersPerUser: number;
  batchSize: number; // Pagination batch size for large datasets
}

@Injectable()
export class RetentionService {
  private readonly logger = new Logger(RetentionService.name);
  private readonly config: RetentionConfig;

  constructor(
    private readonly prisma: PrismaService,
    private readonly kafkaService: KafkaService,
    private readonly connectionsService: ConnectionsService,
    private readonly followUpService: FollowUpService,
    private readonly configService: ConfigService,
  ) {
    this.config = {
      followUpReminderDays: this.configService.get<number>(
        'FOLLOW_UP_REMINDER_DAYS',
        2,
      ),
      staleConnectionDays: this.configService.get<number>(
        'STALE_CONNECTION_DAYS',
        30,
      ),
      digestEnabled: this.configService.get<boolean>(
        'WEEKLY_DIGEST_ENABLED',
        true,
      ),
      maxRemindersPerUser: this.configService.get<number>(
        'MAX_REMINDERS_PER_USER',
        5,
      ),
      batchSize: this.configService.get<number>('RETENTION_BATCH_SIZE', 500),
    };
  }

  /**
   * Daily job: Send follow-up reminders for connections without follow-ups.
   * Runs every day at 9 AM.
   * Uses cursor-based pagination to handle large datasets efficiently.
   */
  @Cron(CronExpression.EVERY_DAY_AT_9AM)
  async sendFollowUpReminders(): Promise<void> {
    this.logger.log('Starting daily follow-up reminder job');

    try {
      const reminderThreshold = new Date();
      reminderThreshold.setDate(
        reminderThreshold.getDate() - this.config.followUpReminderDays,
      );

      // Use cursor-based pagination for memory efficiency
      const userConnectionsMap = new Map<
        string,
        Array<{
          id: string;
          connectedAt: Date;
          userA: { id: string; firstName: string | null; lastName: string | null; email: string };
          userB: { id: string; firstName: string | null; lastName: string | null; email: string };
          userAId: string;
          userBId: string;
        }>
      >();

      let cursor: string | undefined;
      let totalProcessed = 0;

      // Paginate through connections
      while (true) {
        const batch = await this.prisma.connection.findMany({
          where: {
            followUpSentAt: null,
            connectedAt: { lt: reminderThreshold },
          },
          include: {
            userA: {
              select: { id: true, firstName: true, lastName: true, email: true },
            },
            userB: {
              select: { id: true, firstName: true, lastName: true, email: true },
            },
          },
          take: this.config.batchSize,
          ...(cursor && {
            skip: 1,
            cursor: { id: cursor },
          }),
          orderBy: { id: 'asc' },
        });

        if (batch.length === 0) break;

        // Process batch
        for (const conn of batch) {
          for (const userId of [conn.userAId, conn.userBId]) {
            if (!userConnectionsMap.has(userId)) {
              userConnectionsMap.set(userId, []);
            }
            const userConns = userConnectionsMap.get(userId)!;
            if (userConns.length < this.config.maxRemindersPerUser) {
              userConns.push(conn);
            }
          }
        }

        totalProcessed += batch.length;
        cursor = batch[batch.length - 1].id;

        // Safety limit to prevent infinite loops
        if (totalProcessed >= 50000) {
          this.logger.warn(
            `Follow-up reminder job hit safety limit at ${totalProcessed} connections`,
          );
          break;
        }
      }

      // Send reminders
      let remindersSent = 0;
      for (const [userId, connections] of userConnectionsMap) {
        if (connections.length === 0) continue;

        const user =
          connections[0].userAId === userId
            ? connections[0].userA
            : connections[0].userB;

        await this.kafkaService.sendEvent(
          RETENTION_KAFKA_TOPICS.FOLLOW_UP_REMINDER,
          userId,
          {
            userId,
            userEmail: user.email,
            userName: `${user.firstName || ''} ${user.lastName || ''}`.trim(),
            pendingFollowUps: connections.map((c) => ({
              connectionId: c.id,
              otherUserName:
                c.userAId === userId
                  ? `${c.userB.firstName || ''} ${c.userB.lastName || ''}`.trim()
                  : `${c.userA.firstName || ''} ${c.userA.lastName || ''}`.trim(),
              connectedAt: c.connectedAt.toISOString(),
            })),
            sentAt: new Date().toISOString(),
          },
        );

        remindersSent++;
      }

      this.logger.log(
        `Follow-up reminder job completed: ${remindersSent} reminders sent for ${totalProcessed} pending connections`,
      );
    } catch (error) {
      this.logger.error('Follow-up reminder job failed', error);
    }
  }

  /**
   * Weekly job: Nudge users about stale connections that need nurturing.
   * Runs every Monday at 10 AM.
   */
  @Cron('0 10 * * 1') // Monday at 10 AM
  async sendStaleConnectionNudges(): Promise<void> {
    this.logger.log('Starting stale connection nudge job');

    try {
      const staleThreshold = new Date();
      staleThreshold.setDate(
        staleThreshold.getDate() - this.config.staleConnectionDays,
      );

      // Find connections with no recent activity
      const staleConnections = await this.prisma.connection.findMany({
        where: {
          lastInteractionAt: {
            lt: staleThreshold,
          },
          strength: {
            in: ['MODERATE', 'STRONG'], // Only nudge for valuable connections
          },
        },
        include: {
          userA: {
            select: {
              id: true,
              firstName: true,
              lastName: true,
              email: true,
            },
          },
          userB: {
            select: {
              id: true,
              firstName: true,
              lastName: true,
              email: true,
            },
          },
        },
      });

      // Group by user
      const userStaleMap = new Map<
        string,
        Array<(typeof staleConnections)[0]>
      >();

      for (const conn of staleConnections) {
        for (const userId of [conn.userAId, conn.userBId]) {
          if (!userStaleMap.has(userId)) {
            userStaleMap.set(userId, []);
          }
          userStaleMap.get(userId)!.push(conn);
        }
      }

      // Send nudges
      let nudgesSent = 0;
      for (const [userId, connections] of userStaleMap) {
        if (connections.length === 0) continue;

        const user =
          connections[0].userAId === userId
            ? connections[0].userA
            : connections[0].userB;

        await this.kafkaService.sendEvent(
          RETENTION_KAFKA_TOPICS.STALE_CONNECTION_NUDGE,
          userId,
          {
            userId,
            userEmail: user.email,
            userName: `${user.firstName || ''} ${user.lastName || ''}`.trim(),
            staleConnections: connections.slice(0, 5).map((c) => ({
              connectionId: c.id,
              otherUserName:
                c.userAId === userId
                  ? `${c.userB.firstName || ''} ${c.userB.lastName || ''}`.trim()
                  : `${c.userA.firstName || ''} ${c.userA.lastName || ''}`.trim(),
              strength: c.strength,
              lastInteraction: c.lastInteractionAt?.toISOString(),
            })),
            sentAt: new Date().toISOString(),
          },
        );

        nudgesSent++;
      }

      this.logger.log(
        `Stale connection nudge job completed: ${nudgesSent} nudges sent`,
      );
    } catch (error) {
      this.logger.error('Stale connection nudge job failed', error);
    }
  }

  /**
   * Weekly job: Send network digest with stats and highlights.
   * Runs every Sunday at 6 PM.
   */
  @Cron('0 18 * * 0') // Sunday at 6 PM
  async sendWeeklyNetworkDigest(): Promise<void> {
    if (!this.config.digestEnabled) {
      this.logger.log('Weekly digest is disabled, skipping');
      return;
    }

    this.logger.log('Starting weekly network digest job');

    try {
      const weekAgo = new Date();
      weekAgo.setDate(weekAgo.getDate() - 7);

      // Get users with recent connection activity
      const activeUsers = await this.prisma.user.findMany({
        where: {
          OR: [
            {
              connectionsAsUserA: {
                some: {
                  lastInteractionAt: { gte: weekAgo },
                },
              },
            },
            {
              connectionsAsUserB: {
                some: {
                  lastInteractionAt: { gte: weekAgo },
                },
              },
            },
          ],
        },
        select: {
          id: true,
          email: true,
          firstName: true,
          lastName: true,
        },
      });

      let digestsSent = 0;
      for (const user of activeUsers) {
        // Get user's network stats
        const stats = await this.connectionsService.getUserNetworkingStats(
          user.id,
        );
        const distribution =
          await this.connectionsService.getUserStrengthDistribution(user.id);

        // Get new connections this week
        const newConnections = await this.prisma.connection.count({
          where: {
            OR: [{ userAId: user.id }, { userBId: user.id }],
            connectedAt: { gte: weekAgo },
          },
        });

        // Get connections that grew stronger this week
        const strengthenedConnections = await this.prisma.connectionActivity.findMany({
          where: {
            connection: {
              OR: [{ userAId: user.id }, { userBId: user.id }],
            },
            createdAt: { gte: weekAgo },
            activityType: {
              in: [
                'FOLLOW_UP_REPLIED',
                'MEETING_SCHEDULED',
                'MEETING_HELD',
                'OUTCOME_REPORTED',
              ],
            },
          },
          distinct: ['connectionId'],
        });

        await this.kafkaService.sendEvent(
          RETENTION_KAFKA_TOPICS.WEEKLY_NETWORK_DIGEST,
          user.id,
          {
            userId: user.id,
            userEmail: user.email,
            userName: `${user.firstName || ''} ${user.lastName || ''}`.trim(),
            weeklyStats: {
              newConnections,
              totalConnections: stats.totalConnections,
              strongConnections: distribution.STRONG,
              growingConnections: distribution.MODERATE,
              strengthenedThisWeek: strengthenedConnections.length,
              followUpRate: stats.followUpRate,
            },
            sentAt: new Date().toISOString(),
          },
        );

        digestsSent++;
      }

      this.logger.log(
        `Weekly digest job completed: ${digestsSent} digests sent`,
      );
    } catch (error) {
      this.logger.error('Weekly digest job failed', error);
    }
  }

  /**
   * Check and send milestone notifications (e.g., "You've made 10 connections!")
   */
  async checkAndSendMilestone(userId: string): Promise<void> {
    const milestones = [5, 10, 25, 50, 100, 250, 500];

    const connectionCount = await this.prisma.connection.count({
      where: {
        OR: [{ userAId: userId }, { userBId: userId }],
      },
    });

    if (milestones.includes(connectionCount)) {
      const user = await this.prisma.user.findUnique({
        where: { id: userId },
        select: {
          id: true,
          email: true,
          firstName: true,
          lastName: true,
        },
      });

      if (user) {
        await this.kafkaService.sendEvent(
          RETENTION_KAFKA_TOPICS.MILESTONE_NOTIFICATION,
          userId,
          {
            userId,
            userEmail: user.email,
            userName: `${user.firstName || ''} ${user.lastName || ''}`.trim(),
            milestone: connectionCount,
            milestoneType: 'TOTAL_CONNECTIONS',
            sentAt: new Date().toISOString(),
          },
        );

        this.logger.log(
          `Milestone notification sent: User ${userId} reached ${connectionCount} connections`,
        );
      }
    }
  }

  /**
   * Manual trigger for testing cron jobs
   */
  async triggerJob(
    jobName: 'followUpReminders' | 'staleNudges' | 'weeklyDigest',
  ): Promise<{ success: boolean; message: string }> {
    switch (jobName) {
      case 'followUpReminders':
        await this.sendFollowUpReminders();
        return { success: true, message: 'Follow-up reminders job triggered' };
      case 'staleNudges':
        await this.sendStaleConnectionNudges();
        return { success: true, message: 'Stale connection nudges job triggered' };
      case 'weeklyDigest':
        await this.sendWeeklyNetworkDigest();
        return { success: true, message: 'Weekly digest job triggered' };
      default:
        return { success: false, message: 'Unknown job name' };
    }
  }
}
