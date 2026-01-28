// src/leads/lead-broadcast.service.ts
import { Injectable, Logger, Inject } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from '../shared/redis.constants';

export interface LeadData {
  id: string;
  user_id: string;
  user_name: string | null;
  user_email: string | null;
  user_company: string | null;
  user_title: string | null;
  intent_score: number;
  intent_level: 'hot' | 'warm' | 'cold';
  interaction_type: string;
  created_at: string;
}

export interface LeadIntentUpdate {
  lead_id: string;
  intent_score: number;
  intent_level: 'hot' | 'warm' | 'cold';
  interaction_count: number;
}

export interface BoothAnalyticsUpdate {
  eventType: string;
  sponsorId: string;
  timestamp: string;
  stats?: Record<string, unknown>;
}

/**
 * LeadBroadcastService - Broadcasts lead events via Redis Pub/Sub.
 *
 * This service provides multi-instance support by using Redis Pub/Sub
 * instead of direct Socket.IO emissions. All real-time-service instances
 * subscribe to the same channels, ensuring events reach the correct
 * WebSocket clients regardless of which instance they're connected to.
 *
 * Channels:
 * - lead-events: New leads and intent updates for sponsor dashboards
 * - analytics-events: Booth analytics updates for booth staff dashboards
 */
@Injectable()
export class LeadBroadcastService {
  private readonly logger = new Logger(LeadBroadcastService.name);

  // Pub/Sub channels
  private readonly LEAD_EVENTS_CHANNEL = 'lead-events';
  private readonly ANALYTICS_EVENTS_CHANNEL = 'analytics-events';

  constructor(@Inject(REDIS_CLIENT) private readonly redis: Redis) {}

  /**
   * Broadcast a new lead captured event to sponsor dashboard
   * Publishes to Redis Pub/Sub for multi-instance support
   */
  async broadcastNewLead(sponsorId: string, leadData: LeadData): Promise<void> {
    try {
      const payload = {
        type: 'lead.captured.new',
        sponsorId,
        data: leadData,
        timestamp: new Date().toISOString(),
      };

      await this.redis.publish(
        this.LEAD_EVENTS_CHANNEL,
        JSON.stringify(payload),
      );

      this.logger.debug(
        `Broadcasted new lead ${leadData.id} for sponsor ${sponsorId}`,
      );
    } catch (error) {
      this.logger.error(`Failed to broadcast new lead for ${sponsorId}:`, error);
    }
  }

  /**
   * Broadcast a lead intent score update to sponsor dashboard
   */
  async broadcastLeadIntentUpdate(
    sponsorId: string,
    update: LeadIntentUpdate,
  ): Promise<void> {
    try {
      const payload = {
        type: 'lead.intent.updated',
        sponsorId,
        data: update,
        timestamp: new Date().toISOString(),
      };

      await this.redis.publish(
        this.LEAD_EVENTS_CHANNEL,
        JSON.stringify(payload),
      );

      this.logger.debug(
        `Broadcasted intent update for lead ${update.lead_id} to sponsor ${sponsorId}`,
      );
    } catch (error) {
      this.logger.error(
        `Failed to broadcast intent update for ${sponsorId}:`,
        error,
      );
    }
  }

  /**
   * Broadcast booth analytics update to booth staff dashboard
   */
  async broadcastBoothAnalyticsUpdate(
    boothId: string,
    update: BoothAnalyticsUpdate,
  ): Promise<void> {
    try {
      const payload = {
        type: 'expo.booth.analytics.update',
        boothId,
        ...update,
      };

      await this.redis.publish(
        this.ANALYTICS_EVENTS_CHANNEL,
        JSON.stringify(payload),
      );

      this.logger.debug(`Broadcasted analytics update for booth ${boothId}`);
    } catch (error) {
      this.logger.error(
        `Failed to broadcast analytics update for booth ${boothId}:`,
        error,
      );
    }
  }

  /**
   * Broadcast stats update to sponsor dashboard
   * Useful when stats are recalculated and should be pushed immediately
   */
  async broadcastStatsUpdate(
    sponsorId: string,
    stats: {
      total_leads: number;
      hot_leads: number;
      warm_leads: number;
      cold_leads: number;
      leads_contacted: number;
      leads_converted: number;
      conversion_rate: number;
      avg_intent_score: number;
    },
  ): Promise<void> {
    try {
      const payload = {
        type: 'lead.stats.updated',
        sponsorId,
        data: stats,
        timestamp: new Date().toISOString(),
      };

      await this.redis.publish(
        this.LEAD_EVENTS_CHANNEL,
        JSON.stringify(payload),
      );

      this.logger.debug(`Broadcasted stats update for sponsor ${sponsorId}`);
    } catch (error) {
      this.logger.error(
        `Failed to broadcast stats update for ${sponsorId}:`,
        error,
      );
    }
  }

  /**
   * Broadcast bulk lead import completion
   */
  async broadcastBulkImportComplete(
    sponsorId: string,
    importResult: {
      imported: number;
      failed: number;
      duplicates: number;
    },
  ): Promise<void> {
    try {
      const payload = {
        type: 'lead.bulk.imported',
        sponsorId,
        data: importResult,
        timestamp: new Date().toISOString(),
      };

      await this.redis.publish(
        this.LEAD_EVENTS_CHANNEL,
        JSON.stringify(payload),
      );

      this.logger.log(
        `Broadcasted bulk import completion for sponsor ${sponsorId}: ${importResult.imported} imported`,
      );
    } catch (error) {
      this.logger.error(
        `Failed to broadcast bulk import for ${sponsorId}:`,
        error,
      );
    }
  }

  /**
   * Broadcast lead follow-up status change
   */
  async broadcastLeadStatusChange(
    sponsorId: string,
    leadId: string,
    newStatus: string,
    updatedBy: string,
  ): Promise<void> {
    try {
      const payload = {
        type: 'lead.status.changed',
        sponsorId,
        data: {
          lead_id: leadId,
          new_status: newStatus,
          updated_by: updatedBy,
        },
        timestamp: new Date().toISOString(),
      };

      await this.redis.publish(
        this.LEAD_EVENTS_CHANNEL,
        JSON.stringify(payload),
      );

      this.logger.debug(
        `Broadcasted status change for lead ${leadId} to ${newStatus}`,
      );
    } catch (error) {
      this.logger.error(
        `Failed to broadcast status change for lead ${leadId}:`,
        error,
      );
    }
  }
}
