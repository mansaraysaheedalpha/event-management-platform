// src/expo/expo-analytics.service.ts
import { Injectable, Logger } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from 'src/prisma.service';
import { Prisma } from '@prisma/client';
import { firstValueFrom } from 'rxjs';

interface EngagementAction {
  action: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

interface LeadFormData {
  name?: string;
  email?: string;
  company?: string;
  jobTitle?: string;
  phone?: string;
  interests?: string;
  message?: string;
  marketingConsent?: boolean;
}

@Injectable()
export class ExpoAnalyticsService {
  private readonly logger = new Logger(ExpoAnalyticsService.name);
  private readonly eventLifecycleServiceUrl: string;
  private readonly internalApiKey: string;

  constructor(
    private readonly prisma: PrismaService,
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
  ) {
    this.eventLifecycleServiceUrl = this.configService.get<string>(
      'EVENT_LIFECYCLE_SERVICE_URL',
      'http://localhost:8000',
    );
    this.internalApiKey = this.configService.get<string>(
      'INTERNAL_API_KEY',
      '',
    );
  }

  /**
   * Tracks a resource download.
   * Gracefully handles errors to prevent blocking user actions.
   */
  async trackResourceDownload(
    userId: string,
    boothId: string,
    resourceId: string,
    visitId?: string,
  ) {
    try {
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

      this.logger.log(
        `Resource ${resourceId} downloaded from booth ${boothId} by ${userId}`,
      );
    } catch (error) {
      // Log error but don't throw - analytics should never block user actions
      this.logger.error(`Failed to track resource download: ${error}`);
    }
  }

  /**
   * Tracks a CTA button click.
   * Gracefully handles errors to prevent blocking user actions.
   */
  async trackCtaClick(
    userId: string,
    boothId: string,
    ctaId: string,
    visitId?: string,
  ) {
    try {
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
    } catch (error) {
      this.logger.error(`Failed to track CTA click: ${error}`);
    }
  }

  /**
   * Tracks a lead capture.
   * This one throws errors since lead capture is critical for sponsors.
   */
  async trackLeadCapture(
    userId: string,
    boothId: string,
    visitId: string,
    formData: Record<string, unknown>,
  ) {
    try {
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

      // Sync lead to event-lifecycle-service for sponsor dashboard
      await this.syncLeadToEventService(userId, boothId, formData as LeadFormData);

      this.logger.log(`Lead captured in booth ${boothId} from user ${userId}`);
    } catch (error) {
      this.logger.error(`Failed to track lead capture: ${error}`);
      // Re-throw for lead capture since it's business-critical
      throw error;
    }
  }

  /**
   * Syncs a captured lead to the event-lifecycle-service.
   * This creates a SponsorLead record that shows up in the sponsor dashboard.
   */
  private async syncLeadToEventService(
    userId: string,
    boothId: string,
    formData: LeadFormData,
  ) {
    try {
      // Get booth with sponsor and event info
      const booth = await this.prisma.expoBooth.findUnique({
        where: { id: boothId },
        include: {
          expoHall: true,
        },
      });

      if (!booth || !booth.expoHall) {
        this.logger.warn(`Booth ${boothId} or expo hall not found for lead sync`);
        return;
      }

      const sponsorId = booth.sponsorId;
      const eventId = booth.expoHall.eventId;

      if (!sponsorId || !eventId) {
        this.logger.warn(`Missing sponsorId or eventId for booth ${boothId}`);
        return;
      }

      // Ensure URL doesn't have trailing slash
      const baseUrl = this.eventLifecycleServiceUrl.replace(/\/$/, '');
      const url = `${baseUrl}/api/v1/events/${eventId}/sponsors/${sponsorId}/capture-lead`;

      // Build lead data payload
      const leadPayload = {
        user_id: userId,
        user_name: formData.name || null,
        user_email: formData.email || null,
        user_company: formData.company || null,
        user_title: formData.jobTitle || null,
        interaction_type: 'booth_contact_form',
        interaction_metadata: {
          message: formData.message || null,
          phone: formData.phone || null,
          interests: formData.interests || null,
          marketing_consent: formData.marketingConsent || false,
          booth_id: boothId,
          booth_name: booth.name,
        },
      };

      const response = await firstValueFrom(
        this.httpService.post(url, leadPayload, {
          headers: {
            'Content-Type': 'application/json',
            'X-Internal-Api-Key': this.internalApiKey,
          },
          timeout: 5000, // 5 second timeout
        }),
      );

      this.logger.log(
        `Lead synced to event-lifecycle-service for sponsor ${sponsorId}, lead ID: ${response.data?.id}`,
      );
    } catch (error: any) {
      // Log error but don't fail the lead capture
      // The lead is still saved locally in BoothVisit
      const errorMessage = error.response?.data?.detail || error.message;
      this.logger.error(
        `Failed to sync lead to event-lifecycle-service: ${errorMessage}`,
      );
    }
  }

  /**
   * Tracks a video session completion.
   * Gracefully handles errors.
   */
  async trackVideoSession(
    boothId: string,
    durationSeconds: number,
    completed: boolean,
  ) {
    try {
      await this.incrementAnalytics(boothId, 'totalVideoSessions');

      if (completed) {
        await this.incrementAnalytics(boothId, 'completedVideoSessions');
        await this.updateAvgVideoDuration(boothId, durationSeconds);
      }

      this.logger.log(
        `Video session tracked for booth ${boothId} (${durationSeconds}s, completed: ${completed})`,
      );
    } catch (error) {
      this.logger.error(`Failed to track video session: ${error}`);
    }
  }

  /**
   * Tracks a chat message being sent.
   * Gracefully handles errors.
   */
  async trackChatMessage(boothId: string) {
    try {
      await this.incrementAnalytics(boothId, 'totalChatMessages');
    } catch (error) {
      this.logger.error(`Failed to track chat message: ${error}`);
    }
  }

  /**
   * Updates visitor count analytics when someone enters/exits.
   * Gracefully handles errors.
   */
  async updateVisitorMetrics(boothId: string) {
    try {
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
    } catch (error) {
      this.logger.error(`Failed to update visitor metrics: ${error}`);
    }
  }

  /**
   * Updates average visit duration when someone leaves.
   * Gracefully handles errors.
   */
  async updateAvgVisitDuration(boothId: string, durationSeconds: number) {
    try {
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
          (durationSeconds - analytics.avgVisitDuration) /
            analytics.totalVisitors,
      );

      await this.prisma.boothAnalytics.update({
        where: { boothId },
        data: { avgVisitDuration: Math.max(0, newAvg) },
      });
    } catch (error) {
      this.logger.error(`Failed to update avg visit duration: ${error}`);
    }
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
    field:
      | 'totalDownloads'
      | 'totalCtaClicks'
      | 'totalLeads'
      | 'totalChatMessages'
      | 'totalVideoSessions'
      | 'completedVideoSessions',
  ) {
    await this.ensureAnalytics(boothId);

    await this.prisma.boothAnalytics.update({
      where: { boothId },
      data: { [field]: { increment: 1 } },
    });
  }

  private async incrementResourceDownload(boothId: string, resourceId: string) {
    const analytics = await this.ensureAnalytics(boothId);

    const downloads =
      (analytics.resourceDownloads as Record<string, number>) || {};
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

  private async updateAvgVideoDuration(
    boothId: string,
    durationSeconds: number,
  ) {
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
        (durationSeconds - analytics.avgVideoDuration) /
          analytics.completedVideoSessions,
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
