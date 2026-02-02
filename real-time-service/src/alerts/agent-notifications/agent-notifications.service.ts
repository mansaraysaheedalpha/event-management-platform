import { Injectable } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { AgentNotificationPayload } from './dto/agent-notification.dto';
import {
  AgentNotificationType,
  AgentNotificationSeverity,
} from '@prisma/client';

@Injectable()
export class AgentNotificationsService {
  constructor(private readonly prisma: PrismaService) {}

  async createNotification(payload: AgentNotificationPayload) {
    const type =
      payload.type === 'anomaly_detected'
        ? AgentNotificationType.ANOMALY_DETECTED
        : AgentNotificationType.INTERVENTION_EXECUTED;

    const severity =
      payload.type === 'anomaly_detected'
        ? (payload.severity.toUpperCase() as AgentNotificationSeverity)
        : AgentNotificationSeverity.INFO;

    return this.prisma.agentNotification.create({
      data: {
        eventId: payload.event_id,
        sessionId: payload.session_id,
        type,
        severity,
        data: payload as object,
      },
    });
  }

  async getNotifications(
    eventId: string,
    userId: string,
    limit = 50,
    cursor?: string,
  ) {
    const notifications = await this.prisma.agentNotification.findMany({
      where: { eventId },
      take: limit + 1,
      cursor: cursor ? { id: cursor } : undefined,
      orderBy: { createdAt: 'desc' },
      include: {
        readBy: { where: { userId }, select: { readAt: true } },
      },
    });

    const hasMore = notifications.length > limit;
    const items = hasMore ? notifications.slice(0, -1) : notifications;

    return {
      items: items.map((n) => ({
        id: n.id,
        createdAt: n.createdAt,
        eventId: n.eventId,
        sessionId: n.sessionId,
        type: n.type,
        severity: n.severity,
        data: n.data,
        isRead: n.readBy.length > 0,
      })),
      nextCursor: hasMore ? items[items.length - 1].id : null,
    };
  }

  async markAsRead(notificationId: string, userId: string) {
    return this.prisma.agentNotificationRead.upsert({
      where: { userId_notificationId: { userId, notificationId } },
      create: { userId, notificationId },
      update: {},
    });
  }

  async markAllAsRead(eventId: string, userId: string) {
    const unread = await this.prisma.agentNotification.findMany({
      where: {
        eventId,
        readBy: { none: { userId } },
      },
      select: { id: true },
    });

    if (unread.length === 0) return { count: 0 };

    await this.prisma.agentNotificationRead.createMany({
      data: unread.map((n) => ({ userId, notificationId: n.id })),
      skipDuplicates: true,
    });

    return { count: unread.length };
  }

  async getUnreadCount(eventId: string, userId: string): Promise<number> {
    return this.prisma.agentNotification.count({
      where: {
        eventId,
        readBy: { none: { userId } },
      },
    });
  }
}
