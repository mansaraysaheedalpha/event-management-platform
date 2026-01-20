// src/expo/expo-analytics.service.ts
import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { Prisma } from '@prisma/client';

interface EngagementAction {
  action: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

@Injectable()
export class ExpoAnalyticsService {
  private readonly logger = new Logger(ExpoAnalyticsService.name);

  constructor(private readonly prisma: PrismaService) {}

  /**
   * Tracks a resource download.
   */
  async trackResourceDownload(
    userId: string,
    boothId: string,
    resourceId: string,
    visitId?: string,
  ) {
    // Add to visit actions if we have the visit
    if (visitId) {
      await this.addVisitAction(visitId, {
        action: 'resource_download',
        timestamp: new Date().toISOString(),
        metadata: { resourceId },
      });
    }

    // Update booth analytics
    await this.incrementAnalytics(boothId, 'totalDownloads');
    await this.incrementResourceDownload(boothId, resourceId);

    this.logger.log(`Resource ${resourceId} downloaded from booth ${boothId} by ${userId}`);
  }

  /**
   * Tracks a CTA button click.
   */
  async trackCtaClick(
    userId: string,
    boothId: string,
    ctaId: string,
    visitId?: string,
  ) {
    if (visitId) {
      await this.addVisitAction(visitId, {
        action: 'cta_click',
        timestamp: new Date().toISOString(),
        metadata: { ctaId },
      });
    }

    await this.incrementAnalytics(boothId, 'totalCtaClicks');
    await this.incrementCtaClick(boothId, ctaId);

    this.logger.log(`CTA ${ctaId} clicked in booth ${boothId} by ${userId}`);
  }

  /**
   * Tracks a lead capture.
   */
  async trackLeadCapture(
    userId: string,
    boothId: string,
    visitId: string,
    formData: Record<string, unknown>,
  ) {
    // Update the visit with lead data
    await this.prisma.boothVisit.update({
      where: { id: visitId },
      data: {
        leadCaptured: true,
        leadCapturedAt: new Date(),
        leadData: formData as Prisma.InputJsonValue,
      },
    });

    // Add to visit actions
    await this.addVisitAction(visitId, {
      action: 'lead_captured',
      timestamp: new Date().toISOString(),
    });

    // Update booth analytics
    await this.incrementAnalytics(boothId, 'totalLeads');

    this.logger.log(`Lead captured in booth ${boothId} from user ${userId}`);
  }

  /**
   * Tracks a video session completion.
   */
  async trackVideoSession(boothId: string, durationSeconds: number, completed: boolean) {
    await this.incrementAnalytics(boothId, 'totalVideoSessions');

    if (completed) {
      await this.incrementAnalytics(boothId, 'completedVideoSessions');
      await this.updateAvgVideoDuration(boothId, durationSeconds);
    }

    this.logger.log(`Video session tracked for booth ${boothId} (${durationSeconds}s, completed: ${completed})`);
  }

  /**
   * Tracks a chat message being sent.
   */
  async trackChatMessage(boothId: string) {
    await this.incrementAnalytics(boothId, 'totalChatMessages');
  }

  /**
   * Updates visitor count analytics when someone enters/exits.
   */
  async updateVisitorMetrics(boothId: string) {
    const currentCount = await this.prisma.boothVisit.count({
      where: { boothId, exitedAt: null },
    });

    const uniqueCount = await this.prisma.boothVisit.groupBy({
      by: ['userId'],
      where: { boothId },
    });

    const analytics = await this.prisma.boothAnalytics.findUnique({
      where: { boothId },
    });

    const totalVisits = await this.prisma.boothVisit.count({
      where: { boothId },
    });

    await this.prisma.boothAnalytics.upsert({
      where: { boothId },
      create: {
        boothId,
        eventId: await this.getBoothEventId(boothId),
        currentVisitors: currentCount,
        uniqueVisitors: uniqueCount.length,
        totalVisitors: totalVisits,
        peakVisitors: currentCount,
      },
      update: {
        currentVisitors: currentCount,
        uniqueVisitors: uniqueCount.length,
        totalVisitors: totalVisits,
        peakVisitors: analytics
          ? Math.max(analytics.peakVisitors, currentCount)
          : currentCount,
      },
    });
  }

  /**
   * Updates average visit duration when someone leaves.
   */
  async updateAvgVisitDuration(boothId: string, durationSeconds: number) {
    const analytics = await this.ensureAnalytics(boothId);

    // Handle edge cases to avoid division by zero
    if (analytics.totalVisitors <= 0) {
      await this.prisma.boothAnalytics.update({
        where: { boothId },
        data: { avgVisitDuration: durationSeconds },
      });
      return;
    }

    // Calculate running average: new_avg = old_avg + (new_value - old_avg) / count
    // This is more numerically stable than (sum / count)
    const newAvg = Math.floor(
      analytics.avgVisitDuration +
        (durationSeconds - analytics.avgVisitDuration) / analytics.totalVisitors
    );

    await this.prisma.boothAnalytics.update({
      where: { boothId },
      data: { avgVisitDuration: Math.max(0, newAvg) },
    });
  }

  /**
   * Gets analytics summary for a booth.
   */
  async getBoothAnalytics(boothId: string) {
    const analytics = await this.prisma.boothAnalytics.findUnique({
      where: { boothId },
    });

    if (!analytics) {
      // Return default values
      return {
        currentVisitors: 0,
        totalVisitors: 0,
        uniqueVisitors: 0,
        peakVisitors: 0,
        avgVisitDuration: 0,
        totalChatMessages: 0,
        totalVideoSessions: 0,
        completedVideoSessions: 0,
        avgVideoDuration: 0,
        totalDownloads: 0,
        totalCtaClicks: 0,
        totalLeads: 0,
        resourceDownloads: {},
        ctaClicks: {},
      };
    }

    return analytics;
  }

  /**
   * Gets real-time stats for sponsor dashboard.
   */
  async getRealtimeStats(boothId: string) {
    const [analytics, activeVisits, pendingVideoRequests] = await Promise.all([
      this.getBoothAnalytics(boothId),
      this.prisma.boothVisit.findMany({
        where: { boothId, exitedAt: null },
        select: {
          userId: true,
          enteredAt: true,
          status: true,
        },
      }),
      this.prisma.boothVideoSession.count({
        where: { boothId, status: 'REQUESTED' },
      }),
    ]);

    return {
      ...analytics,
      currentVisitors: activeVisits.length,
      pendingVideoRequests,
      visitors: activeVisits,
    };
  }

  // Private helper methods

  private async addVisitAction(visitId: string, action: EngagementAction) {
    const visit = await this.prisma.boothVisit.findUnique({
      where: { id: visitId },
      select: { actions: true },
    });

    if (!visit) return;

    const existingActions = Array.isArray(visit.actions) ? visit.actions : [];
    const actions = [...existingActions, action];

    await this.prisma.boothVisit.update({
      where: { id: visitId },
      data: { actions: actions as Prisma.InputJsonValue },
    });
  }

  private async incrementAnalytics(
    boothId: string,
    field: 'totalDownloads' | 'totalCtaClicks' | 'totalLeads' | 'totalChatMessages' | 'totalVideoSessions' | 'completedVideoSessions',
  ) {
    await this.ensureAnalytics(boothId);

    await this.prisma.boothAnalytics.update({
      where: { boothId },
      data: { [field]: { increment: 1 } },
    });
  }

  private async incrementResourceDownload(boothId: string, resourceId: string) {
    const analytics = await this.ensureAnalytics(boothId);

    const downloads = (analytics.resourceDownloads as Record<string, number>) || {};
    downloads[resourceId] = (downloads[resourceId] || 0) + 1;

    await this.prisma.boothAnalytics.update({
      where: { boothId },
      data: { resourceDownloads: downloads },
    });
  }

  private async incrementCtaClick(boothId: string, ctaId: string) {
    const analytics = await this.ensureAnalytics(boothId);

    const clicks = (analytics.ctaClicks as Record<string, number>) || {};
    clicks[ctaId] = (clicks[ctaId] || 0) + 1;

    await this.prisma.boothAnalytics.update({
      where: { boothId },
      data: { ctaClicks: clicks },
    });
  }

  private async updateAvgVideoDuration(boothId: string, durationSeconds: number) {
    const analytics = await this.ensureAnalytics(boothId);

    // Handle edge cases to avoid division by zero
    if (analytics.completedVideoSessions <= 0) {
      await this.prisma.boothAnalytics.update({
        where: { boothId },
        data: { avgVideoDuration: durationSeconds },
      });
      return;
    }

    // Calculate running average: new_avg = old_avg + (new_value - old_avg) / count
    const newAvg = Math.floor(
      analytics.avgVideoDuration +
        (durationSeconds - analytics.avgVideoDuration) / analytics.completedVideoSessions
    );

    await this.prisma.boothAnalytics.update({
      where: { boothId },
      data: { avgVideoDuration: Math.max(0, newAvg) },
    });
  }

  private async ensureAnalytics(boothId: string) {
    let analytics = await this.prisma.boothAnalytics.findUnique({
      where: { boothId },
    });

    if (!analytics) {
      analytics = await this.prisma.boothAnalytics.create({
        data: {
          boothId,
          eventId: await this.getBoothEventId(boothId),
        },
      });
    }

    return analytics;
  }

  private async getBoothEventId(boothId: string): Promise<string> {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
      include: { expoHall: true },
    });

    return booth?.expoHall?.eventId || '';
  }
}
