//src/networking/recommendations/recommendations.scheduler.ts
import { Injectable, Logger, OnModuleInit, OnModuleDestroy } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from 'src/prisma.service';
import { RecommendationsService } from './recommendations.service';

/**
 * RecommendationsScheduler handles periodic tasks for recommendation system.
 *
 * Tasks:
 * - Daily refresh of recommendations for active users
 * - Cleanup of expired recommendations
 *
 * Note: This uses setInterval for simplicity. For production, consider using
 * @nestjs/schedule with a proper cron expression for more precise scheduling.
 */
@Injectable()
export class RecommendationsScheduler implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(RecommendationsScheduler.name);
  private dailyRefreshInterval: NodeJS.Timeout | null = null;
  private cleanupInterval: NodeJS.Timeout | null = null;

  // Interval timing (in milliseconds)
  private readonly DAILY_REFRESH_INTERVAL = 24 * 60 * 60 * 1000; // 24 hours
  private readonly CLEANUP_INTERVAL = 6 * 60 * 60 * 1000; // 6 hours

  constructor(
    private readonly prisma: PrismaService,
    private readonly recommendationsService: RecommendationsService,
    private readonly configService: ConfigService,
  ) {}

  onModuleInit(): void {
    const enableScheduler = this.configService.get<boolean>(
      'ENABLE_RECOMMENDATION_SCHEDULER',
      false,
    );

    if (enableScheduler) {
      this.startScheduledTasks();
      this.logger.log('Recommendation scheduler started');
    } else {
      this.logger.log(
        'Recommendation scheduler disabled (set ENABLE_RECOMMENDATION_SCHEDULER=true to enable)',
      );
    }
  }

  onModuleDestroy(): void {
    this.stopScheduledTasks();
  }

  /**
   * Start all scheduled tasks
   */
  private startScheduledTasks(): void {
    // Daily refresh task
    this.dailyRefreshInterval = setInterval(() => {
      this.runDailyRefresh().catch((err) => {
        this.logger.error('Daily refresh failed:', err);
      });
    }, this.DAILY_REFRESH_INTERVAL);

    // Cleanup task
    this.cleanupInterval = setInterval(() => {
      this.cleanupExpiredRecommendations().catch((err) => {
        this.logger.error('Cleanup failed:', err);
      });
    }, this.CLEANUP_INTERVAL);

    // Run cleanup immediately on startup
    this.cleanupExpiredRecommendations().catch((err) => {
      this.logger.error('Initial cleanup failed:', err);
    });
  }

  /**
   * Stop all scheduled tasks
   */
  private stopScheduledTasks(): void {
    if (this.dailyRefreshInterval) {
      clearInterval(this.dailyRefreshInterval);
      this.dailyRefreshInterval = null;
    }
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.logger.log('Recommendation scheduler stopped');
  }

  /**
   * Daily refresh of recommendations for users who were active recently.
   * This ensures recommendations stay fresh for engaged users.
   */
  async runDailyRefresh(): Promise<void> {
    this.logger.log('Starting daily recommendation refresh...');

    const startTime = Date.now();
    let refreshedCount = 0;

    try {
      // Find users with recommendations that are expiring soon (within 6 hours)
      // and have been active in the last 24 hours
      const soonExpiringRecs = await this.prisma.recommendation.findMany({
        where: {
          expiresAt: {
            lte: new Date(Date.now() + 6 * 60 * 60 * 1000), // Expiring in 6 hours
          },
        },
        select: {
          userId: true,
          eventId: true,
        },
        distinct: ['userId', 'eventId'],
        take: 100, // Limit batch size
      });

      // Get unique user-event pairs
      const uniquePairs = new Map<string, { userId: string; eventId: string }>();
      for (const rec of soonExpiringRecs) {
        const key = `${rec.userId}:${rec.eventId}`;
        if (!uniquePairs.has(key)) {
          uniquePairs.set(key, rec);
        }
      }

      // Trigger refresh for each user-event pair
      for (const { userId, eventId } of uniquePairs.values()) {
        try {
          await this.recommendationsService.triggerRecommendationGeneration(
            userId,
            eventId,
          );
          refreshedCount++;

          // Add a small delay to avoid overwhelming the oracle service
          await this.sleep(500);
        } catch (error) {
          this.logger.warn(
            `Failed to refresh recommendations for user ${userId} at event ${eventId}: ${error}`,
          );
        }
      }

      const duration = Date.now() - startTime;
      this.logger.log(
        `Daily refresh completed: ${refreshedCount} user-event pairs refreshed in ${duration}ms`,
      );
    } catch (error) {
      this.logger.error('Daily refresh task failed:', error);
    }
  }

  /**
   * Clean up expired recommendations from the database.
   * This prevents database bloat from old recommendations.
   */
  async cleanupExpiredRecommendations(): Promise<void> {
    this.logger.log('Starting expired recommendations cleanup...');

    try {
      const result = await this.prisma.recommendation.deleteMany({
        where: {
          expiresAt: {
            lt: new Date(), // Already expired
          },
        },
      });

      this.logger.log(
        `Cleanup completed: ${result.count} expired recommendations deleted`,
      );
    } catch (error) {
      this.logger.error('Cleanup task failed:', error);
    }
  }

  /**
   * Manual trigger endpoint for running daily refresh.
   * Can be called from an admin endpoint or external cron service.
   */
  async triggerManualRefresh(): Promise<{ refreshedCount: number }> {
    await this.runDailyRefresh();
    return { refreshedCount: 0 }; // Actual count is logged, not returned
  }

  /**
   * Helper to add delay between operations
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
