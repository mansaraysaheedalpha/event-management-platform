// src/leads/lead-stats-cache.service.ts
import { Injectable, Logger, Inject } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from '../shared/redis.constants';

export interface LeadStats {
  total_leads: number;
  hot_leads: number;
  warm_leads: number;
  cold_leads: number;
  leads_contacted: number;
  leads_converted: number;
  conversion_rate: number;
  avg_intent_score: number;
  cached_at: string;
}

export interface LeadStatsIncrement {
  sponsorId: string;
  intentLevel: 'hot' | 'warm' | 'cold';
}

/**
 * LeadStatsCacheService - Redis-based caching for lead statistics.
 *
 * Provides:
 * - Fast cached stats retrieval (O(1) lookup)
 * - Atomic counter increments for real-time updates
 * - TTL-based cache invalidation
 * - Distributed cache across multiple instances
 */
@Injectable()
export class LeadStatsCacheService {
  private readonly logger = new Logger(LeadStatsCacheService.name);

  // Cache configuration
  private readonly STATS_KEY_PREFIX = 'lead:stats:';
  private readonly COUNTER_KEY_PREFIX = 'lead:counter:';
  private readonly STATS_TTL_SECONDS = 30; // Cache stats for 30 seconds
  private readonly COUNTER_TTL_SECONDS = 3600; // Keep counters for 1 hour

  constructor(@Inject(REDIS_CLIENT) private readonly redis: Redis) {}

  /**
   * Get cached stats for a sponsor
   * Returns null if cache miss or expired
   */
  async getCachedStats(sponsorId: string): Promise<LeadStats | null> {
    try {
      const key = `${this.STATS_KEY_PREFIX}${sponsorId}`;
      const cached = await this.redis.get(key);

      if (!cached) {
        return null;
      }

      const stats: LeadStats = JSON.parse(cached);

      // Enhance with real-time counters if available
      const counters = await this.getRealtimeCounters(sponsorId);
      if (counters) {
        // Add incremental updates to cached base values
        return {
          ...stats,
          total_leads: stats.total_leads + (counters.total || 0),
          hot_leads: stats.hot_leads + (counters.hot || 0),
          warm_leads: stats.warm_leads + (counters.warm || 0),
          cold_leads: stats.cold_leads + (counters.cold || 0),
        };
      }

      return stats;
    } catch (error) {
      this.logger.error(`Failed to get cached stats for ${sponsorId}:`, error);
      return null;
    }
  }

  /**
   * Store stats in cache with TTL
   */
  async setCachedStats(sponsorId: string, stats: LeadStats): Promise<void> {
    try {
      const key = `${this.STATS_KEY_PREFIX}${sponsorId}`;
      const payload = {
        ...stats,
        cached_at: new Date().toISOString(),
      };

      await this.redis.setex(key, this.STATS_TTL_SECONDS, JSON.stringify(payload));

      // Reset counters when we cache fresh stats
      await this.resetCounters(sponsorId);

      this.logger.debug(`Stats cached for sponsor ${sponsorId}`);
    } catch (error) {
      this.logger.error(`Failed to cache stats for ${sponsorId}:`, error);
    }
  }

  /**
   * Invalidate cached stats for a sponsor
   * Forces next request to fetch from database
   */
  async invalidateStats(sponsorId: string): Promise<void> {
    try {
      const key = `${this.STATS_KEY_PREFIX}${sponsorId}`;
      await this.redis.del(key);
      this.logger.debug(`Stats cache invalidated for sponsor ${sponsorId}`);
    } catch (error) {
      this.logger.error(`Failed to invalidate stats for ${sponsorId}:`, error);
    }
  }

  /**
   * Atomically increment lead count for a sponsor by intent level
   * Used for real-time counter updates between cache refreshes
   */
  async incrementLeadCount(
    sponsorId: string,
    intentLevel: 'hot' | 'warm' | 'cold',
  ): Promise<void> {
    try {
      const pipeline = this.redis.pipeline();

      // Increment total counter
      const totalKey = `${this.COUNTER_KEY_PREFIX}${sponsorId}:total`;
      pipeline.incr(totalKey);
      pipeline.expire(totalKey, this.COUNTER_TTL_SECONDS);

      // Increment intent-specific counter
      const intentKey = `${this.COUNTER_KEY_PREFIX}${sponsorId}:${intentLevel}`;
      pipeline.incr(intentKey);
      pipeline.expire(intentKey, this.COUNTER_TTL_SECONDS);

      await pipeline.exec();

      this.logger.debug(
        `Incremented ${intentLevel} lead counter for sponsor ${sponsorId}`,
      );
    } catch (error) {
      this.logger.error(`Failed to increment lead count for ${sponsorId}:`, error);
    }
  }

  /**
   * Decrement lead count (for corrections or deletions)
   */
  async decrementLeadCount(
    sponsorId: string,
    intentLevel: 'hot' | 'warm' | 'cold',
  ): Promise<void> {
    try {
      const pipeline = this.redis.pipeline();

      const totalKey = `${this.COUNTER_KEY_PREFIX}${sponsorId}:total`;
      pipeline.decr(totalKey);

      const intentKey = `${this.COUNTER_KEY_PREFIX}${sponsorId}:${intentLevel}`;
      pipeline.decr(intentKey);

      await pipeline.exec();
    } catch (error) {
      this.logger.error(`Failed to decrement lead count for ${sponsorId}:`, error);
    }
  }

  /**
   * Get real-time counters for a sponsor
   * These track incremental changes since last cache refresh
   */
  async getRealtimeCounters(
    sponsorId: string,
  ): Promise<{ total: number; hot: number; warm: number; cold: number } | null> {
    try {
      const pipeline = this.redis.pipeline();

      pipeline.get(`${this.COUNTER_KEY_PREFIX}${sponsorId}:total`);
      pipeline.get(`${this.COUNTER_KEY_PREFIX}${sponsorId}:hot`);
      pipeline.get(`${this.COUNTER_KEY_PREFIX}${sponsorId}:warm`);
      pipeline.get(`${this.COUNTER_KEY_PREFIX}${sponsorId}:cold`);

      const results = await pipeline.exec();

      if (!results) {
        return null;
      }

      const [totalResult, hotResult, warmResult, coldResult] = results;

      // Check if any counters exist
      const total = totalResult?.[1] ? parseInt(totalResult[1] as string, 10) : 0;
      const hot = hotResult?.[1] ? parseInt(hotResult[1] as string, 10) : 0;
      const warm = warmResult?.[1] ? parseInt(warmResult[1] as string, 10) : 0;
      const cold = coldResult?.[1] ? parseInt(coldResult[1] as string, 10) : 0;

      // Return null if no counters exist
      if (total === 0 && hot === 0 && warm === 0 && cold === 0) {
        return null;
      }

      return { total, hot, warm, cold };
    } catch (error) {
      this.logger.error(`Failed to get counters for ${sponsorId}:`, error);
      return null;
    }
  }

  /**
   * Reset real-time counters for a sponsor
   * Called after caching fresh stats from database
   */
  private async resetCounters(sponsorId: string): Promise<void> {
    try {
      const pipeline = this.redis.pipeline();

      pipeline.del(`${this.COUNTER_KEY_PREFIX}${sponsorId}:total`);
      pipeline.del(`${this.COUNTER_KEY_PREFIX}${sponsorId}:hot`);
      pipeline.del(`${this.COUNTER_KEY_PREFIX}${sponsorId}:warm`);
      pipeline.del(`${this.COUNTER_KEY_PREFIX}${sponsorId}:cold`);

      await pipeline.exec();
    } catch (error) {
      this.logger.error(`Failed to reset counters for ${sponsorId}:`, error);
    }
  }

  /**
   * Check if stats are cached for a sponsor
   */
  async hasCachedStats(sponsorId: string): Promise<boolean> {
    try {
      const key = `${this.STATS_KEY_PREFIX}${sponsorId}`;
      const exists = await this.redis.exists(key);
      return exists === 1;
    } catch (error) {
      this.logger.error(`Failed to check cache for ${sponsorId}:`, error);
      return false;
    }
  }

  /**
   * Get cache TTL remaining for a sponsor's stats
   * Returns -1 if no TTL, -2 if key doesn't exist
   */
  async getCacheTTL(sponsorId: string): Promise<number> {
    try {
      const key = `${this.STATS_KEY_PREFIX}${sponsorId}`;
      return await this.redis.ttl(key);
    } catch (error) {
      this.logger.error(`Failed to get TTL for ${sponsorId}:`, error);
      return -2;
    }
  }

  /**
   * Warm up cache for multiple sponsors
   * Useful for pre-loading stats when event starts
   */
  async warmUpCache(
    sponsorStats: Array<{ sponsorId: string; stats: LeadStats }>,
  ): Promise<void> {
    try {
      const pipeline = this.redis.pipeline();

      for (const { sponsorId, stats } of sponsorStats) {
        const key = `${this.STATS_KEY_PREFIX}${sponsorId}`;
        const payload = {
          ...stats,
          cached_at: new Date().toISOString(),
        };
        pipeline.setex(key, this.STATS_TTL_SECONDS, JSON.stringify(payload));
      }

      await pipeline.exec();

      this.logger.log(`Warmed up cache for ${sponsorStats.length} sponsors`);
    } catch (error) {
      this.logger.error('Failed to warm up cache:', error);
    }
  }
}
