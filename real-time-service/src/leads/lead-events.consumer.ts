// src/leads/lead-events.consumer.ts
import {
  Injectable,
  Logger,
  OnModuleInit,
  OnModuleDestroy,
  Inject,
} from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from '../shared/redis.constants';
import { LeadBroadcastService } from './lead-broadcast.service';
import { LeadStatsCacheService } from './lead-stats-cache.service';

export interface LeadCapturedEvent {
  type: 'LEAD_CAPTURED' | 'LEAD_INTENT_UPDATED';
  sponsorId: string;
  eventId: string;
  leadId?: string;
  userId?: string;
  boothId?: string;
  data: {
    id: string;
    user_id: string;
    user_name: string | null;
    user_email: string | null;
    user_company: string | null;
    user_title: string | null;
    intent_score: number;
    intent_level: 'hot' | 'warm' | 'cold';
    interaction_type: string;
    interaction_count: number;
    first_interaction_at: string;
    last_interaction_at: string;
    created_at: string;
  };
  timestamp: string;
}

/**
 * LeadEventsConsumer - Consumes lead events from Redis Streams with consumer groups.
 *
 * This provides guaranteed delivery of lead events:
 * - Uses XREADGROUP for consumer group support
 * - Acknowledges messages after successful processing (XACK)
 * - Failed messages remain pending and can be reclaimed
 * - Multiple instances can share the workload
 */
@Injectable()
export class LeadEventsConsumer implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(LeadEventsConsumer.name);

  // Stream configuration
  private readonly STREAM_NAME = 'platform.leads.events.v1';
  private readonly CONSUMER_GROUP = 'lead-metrics-consumer-group';
  private readonly CONSUMER_ID = `consumer-${process.pid}-${Date.now()}`;

  // Consumer settings
  private readonly BLOCK_TIMEOUT_MS = 5000; // Block for 5 seconds waiting for messages
  private readonly BATCH_SIZE = 10; // Process up to 10 messages at a time
  private readonly PENDING_CHECK_INTERVAL_MS = 30000; // Check for pending messages every 30s
  private readonly PENDING_CLAIM_TIMEOUT_MS = 60000; // Claim messages pending for > 1 minute

  private isRunning = false;
  private consumerLoop: Promise<void> | null = null;
  private pendingCheckInterval: NodeJS.Timeout | null = null;

  constructor(
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly broadcastService: LeadBroadcastService,
    private readonly statsCacheService: LeadStatsCacheService,
  ) {}

  async onModuleInit() {
    await this.createConsumerGroup();
    this.startConsuming();
    this.startPendingMessageChecker();
    this.logger.log(`Lead events consumer started: ${this.CONSUMER_ID}`);
  }

  async onModuleDestroy() {
    this.isRunning = false;

    if (this.pendingCheckInterval) {
      clearInterval(this.pendingCheckInterval);
      this.pendingCheckInterval = null;
    }

    // Wait for consumer loop to finish
    if (this.consumerLoop) {
      await this.consumerLoop;
    }

    this.logger.log('Lead events consumer stopped');
  }

  /**
   * Create consumer group if it doesn't exist
   */
  private async createConsumerGroup(): Promise<void> {
    try {
      // Create stream and consumer group
      // MKSTREAM creates the stream if it doesn't exist
      // '0' means start from the beginning of the stream
      await this.redis.xgroup(
        'CREATE',
        this.STREAM_NAME,
        this.CONSUMER_GROUP,
        '0',
        'MKSTREAM',
      );
      this.logger.log(`Consumer group '${this.CONSUMER_GROUP}' created`);
    } catch (error: any) {
      // BUSYGROUP error means group already exists - that's fine
      if (error.message?.includes('BUSYGROUP')) {
        this.logger.debug(`Consumer group '${this.CONSUMER_GROUP}' already exists`);
      } else {
        this.logger.error('Failed to create consumer group:', error);
        throw error;
      }
    }
  }

  /**
   * Start the main consumer loop
   */
  private startConsuming(): void {
    this.isRunning = true;
    this.consumerLoop = this.consumeLoop();
  }

  /**
   * Main consumer loop - reads and processes messages
   */
  private async consumeLoop(): Promise<void> {
    while (this.isRunning) {
      try {
        // XREADGROUP reads new messages for this consumer
        // '>' means only messages that haven't been delivered to any consumer yet
        const result = await this.redis.xreadgroup(
          'GROUP',
          this.CONSUMER_GROUP,
          this.CONSUMER_ID,
          'COUNT',
          this.BATCH_SIZE,
          'BLOCK',
          this.BLOCK_TIMEOUT_MS,
          'STREAMS',
          this.STREAM_NAME,
          '>',
        ) as [string, [string, string[]][]][] | null;

        if (!result || result.length === 0) {
          continue; // No messages, continue waiting
        }

        // Process messages from the stream
        // Result format: [[streamName, [[messageId, [field, value, ...]], ...]]]
        for (const [, messages] of result) {
          for (const [messageId, fields] of messages) {
            await this.processMessage(messageId, fields);
          }
        }
      } catch (error) {
        if (this.isRunning) {
          this.logger.error('Error in consumer loop:', error);
          // Brief pause before retrying
          await this.sleep(1000);
        }
      }
    }
  }

  /**
   * Process a single message from the stream
   */
  private async processMessage(
    messageId: string,
    fields: string[],
  ): Promise<void> {
    try {
      // Fields come as ['data', '{"type":"LEAD_CAPTURED",...}']
      const dataIndex = fields.indexOf('data');
      if (dataIndex === -1 || !fields[dataIndex + 1]) {
        this.logger.warn(`Invalid message format: ${messageId}`);
        await this.acknowledgeMessage(messageId);
        return;
      }

      const payload: LeadCapturedEvent = JSON.parse(fields[dataIndex + 1]);

      this.logger.debug(`Processing lead event: ${payload.type} for sponsor ${payload.sponsorId}`);

      // Handle different event types
      switch (payload.type) {
        case 'LEAD_CAPTURED':
          await this.handleLeadCaptured(payload);
          break;
        case 'LEAD_INTENT_UPDATED':
          await this.handleLeadIntentUpdated(payload);
          break;
        default:
          this.logger.warn(`Unknown event type: ${payload.type}`);
      }

      // Acknowledge successful processing
      await this.acknowledgeMessage(messageId);

    } catch (error) {
      this.logger.error(`Failed to process message ${messageId}:`, error);
      // Don't acknowledge - message will be reclaimed later
      // This provides at-least-once delivery guarantee
    }
  }

  /**
   * Handle LEAD_CAPTURED event
   */
  private async handleLeadCaptured(event: LeadCapturedEvent): Promise<void> {
    const { sponsorId, data, boothId } = event;

    // 1. Invalidate cached stats (will be recalculated on next request)
    await this.statsCacheService.invalidateStats(sponsorId);

    // 2. Increment real-time counters
    await this.statsCacheService.incrementLeadCount(sponsorId, data.intent_level);

    // 3. Broadcast to sponsor dashboard via WebSocket
    this.broadcastService.broadcastNewLead(sponsorId, {
      id: data.id,
      user_id: data.user_id,
      user_name: data.user_name,
      user_email: data.user_email,
      user_company: data.user_company,
      user_title: data.user_title,
      intent_score: data.intent_score,
      intent_level: data.intent_level,
      interaction_type: data.interaction_type,
      created_at: data.created_at,
    });

    // 4. Broadcast booth analytics update if boothId is available
    if (boothId) {
      this.broadcastService.broadcastBoothAnalyticsUpdate(boothId, {
        eventType: 'LEAD_CAPTURED',
        sponsorId,
        timestamp: event.timestamp,
      });
    }

    this.logger.log(
      `Lead captured event processed for sponsor ${sponsorId}, lead ${data.id}`,
    );
  }

  /**
   * Handle LEAD_INTENT_UPDATED event
   */
  private async handleLeadIntentUpdated(event: LeadCapturedEvent): Promise<void> {
    const { sponsorId, data, leadId } = event;

    // 1. Invalidate cached stats
    await this.statsCacheService.invalidateStats(sponsorId);

    // 2. Broadcast intent update to sponsor dashboard
    this.broadcastService.broadcastLeadIntentUpdate(sponsorId, {
      lead_id: leadId || data.id,
      intent_score: data.intent_score,
      intent_level: data.intent_level,
      interaction_count: data.interaction_count,
    });

    this.logger.log(
      `Lead intent updated event processed for sponsor ${sponsorId}, lead ${leadId || data.id}`,
    );
  }

  /**
   * Acknowledge message as processed
   */
  private async acknowledgeMessage(messageId: string): Promise<void> {
    try {
      await this.redis.xack(this.STREAM_NAME, this.CONSUMER_GROUP, messageId);
    } catch (error) {
      this.logger.error(`Failed to acknowledge message ${messageId}:`, error);
    }
  }

  /**
   * Start periodic check for pending (failed) messages
   */
  private startPendingMessageChecker(): void {
    this.pendingCheckInterval = setInterval(async () => {
      await this.claimPendingMessages();
    }, this.PENDING_CHECK_INTERVAL_MS);
  }

  /**
   * Claim and reprocess messages that have been pending too long
   */
  private async claimPendingMessages(): Promise<void> {
    try {
      // XPENDING shows messages that haven't been acknowledged
      // Returns: [[messageId, consumer, idleTime, deliveryCount], ...]
      const pending = await this.redis.xpending(
        this.STREAM_NAME,
        this.CONSUMER_GROUP,
        '-',
        '+',
        10, // Check up to 10 pending messages
      ) as [string, string, number, number][];

      if (!pending || pending.length === 0) {
        return;
      }

      // Claim messages that have been pending longer than threshold
      for (const entry of pending) {
        const [messageId, consumer, idleTime] = entry;
        if (Number(idleTime) > this.PENDING_CLAIM_TIMEOUT_MS) {
          this.logger.log(
            `Claiming pending message ${messageId} from ${consumer} (idle: ${idleTime}ms)`,
          );

          // XCLAIM transfers ownership of the message to this consumer
          // Returns: [[messageId, [field, value, ...]], ...]
          const claimed = await this.redis.xclaim(
            this.STREAM_NAME,
            this.CONSUMER_GROUP,
            this.CONSUMER_ID,
            this.PENDING_CLAIM_TIMEOUT_MS,
            messageId,
          ) as [string, string[]][];

          // Reprocess claimed messages
          for (const claimedEntry of claimed) {
            const [claimedId, fields] = claimedEntry;
            await this.processMessage(claimedId, fields);
          }
        }
      }
    } catch (error) {
      this.logger.error('Error claiming pending messages:', error);
    }
  }

  /**
   * Utility: sleep for specified milliseconds
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
