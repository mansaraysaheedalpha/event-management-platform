// src/leads/leads.listener.ts
import {
  Injectable,
  Logger,
  OnModuleInit,
  OnModuleDestroy,
  Inject,
} from '@nestjs/common';
import { Redis } from 'ioredis';
import { ConfigService } from '@nestjs/config';
import { SponsorsGateway } from '../monetization/sponsors/sponsors.gateway';
import { Server } from 'socket.io';

/**
 * LeadsListener - Subscribes to Redis Pub/Sub channels and emits WebSocket events.
 *
 * This service bridges Redis Pub/Sub with Socket.IO:
 * - Subscribes to lead-events and analytics-events channels
 * - Emits WebSocket events to the appropriate rooms
 * - Supports multi-instance deployments (all instances receive broadcasts)
 */
@Injectable()
export class LeadsListener implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(LeadsListener.name);
  private subscriber: Redis;

  // Pub/Sub channels to subscribe
  private readonly LEAD_EVENTS_CHANNEL = 'lead-events';
  private readonly ANALYTICS_EVENTS_CHANNEL = 'analytics-events';

  constructor(
    private readonly configService: ConfigService,
    private readonly sponsorsGateway: SponsorsGateway,
  ) {}

  async onModuleInit() {
    // Create a dedicated Redis connection for subscribing
    // (subscribers can't publish on the same connection)
    const redisUrl = this.configService.getOrThrow<string>('REDIS_URL');
    this.subscriber = new Redis(redisUrl);

    // Subscribe to channels
    await this.subscriber.subscribe(
      this.LEAD_EVENTS_CHANNEL,
      this.ANALYTICS_EVENTS_CHANNEL,
    );

    // Handle incoming messages
    this.subscriber.on('message', (channel, message) => {
      this.handleMessage(channel, message);
    });

    this.logger.log('Leads listener subscribed to Redis Pub/Sub channels');
  }

  async onModuleDestroy() {
    if (this.subscriber) {
      await this.subscriber.unsubscribe(
        this.LEAD_EVENTS_CHANNEL,
        this.ANALYTICS_EVENTS_CHANNEL,
      );
      await this.subscriber.quit();
    }
    this.logger.log('Leads listener unsubscribed from Redis Pub/Sub channels');
  }

  /**
   * Handle incoming Pub/Sub messages
   */
  private handleMessage(channel: string, message: string): void {
    try {
      const payload = JSON.parse(message);

      switch (channel) {
        case this.LEAD_EVENTS_CHANNEL:
          this.handleLeadEvent(payload);
          break;
        case this.ANALYTICS_EVENTS_CHANNEL:
          this.handleAnalyticsEvent(payload);
          break;
        default:
          this.logger.warn(`Unknown channel: ${channel}`);
      }
    } catch (error) {
      this.logger.error(`Failed to process message from ${channel}:`, error);
    }
  }

  /**
   * Handle lead events and emit to WebSocket
   */
  private handleLeadEvent(payload: {
    type: string;
    sponsorId: string;
    data: any;
    timestamp: string;
  }): void {
    const { type, sponsorId, data } = payload;

    // Get the Socket.IO server from the gateway
    const server: Server = this.sponsorsGateway.server;
    if (!server) {
      this.logger.warn('WebSocket server not available for lead event');
      return;
    }

    const sponsorRoom = `sponsor:${sponsorId}`;

    switch (type) {
      case 'lead.captured.new':
        server.to(sponsorRoom).emit('lead.captured.new', data);
        this.logger.debug(`Emitted lead.captured.new to ${sponsorRoom}`);
        break;

      case 'lead.intent.updated':
        server.to(sponsorRoom).emit('lead.intent.updated', data);
        this.logger.debug(`Emitted lead.intent.updated to ${sponsorRoom}`);
        break;

      case 'lead.stats.updated':
        server.to(sponsorRoom).emit('lead.stats.updated', data);
        this.logger.debug(`Emitted lead.stats.updated to ${sponsorRoom}`);
        break;

      case 'lead.status.changed':
        server.to(sponsorRoom).emit('lead.status.changed', data);
        this.logger.debug(`Emitted lead.status.changed to ${sponsorRoom}`);
        break;

      case 'lead.bulk.imported':
        server.to(sponsorRoom).emit('lead.bulk.imported', data);
        this.logger.debug(`Emitted lead.bulk.imported to ${sponsorRoom}`);
        break;

      default:
        this.logger.warn(`Unknown lead event type: ${type}`);
    }
  }

  /**
   * Handle analytics events and emit to WebSocket
   */
  private handleAnalyticsEvent(payload: {
    type: string;
    boothId: string;
    sponsorId?: string;
    eventType?: string;
    stats?: any;
    timestamp?: string;
  }): void {
    const { type, boothId, sponsorId, stats } = payload;

    // Get the Socket.IO server from the gateway
    const server: Server = this.sponsorsGateway.server;
    if (!server) {
      this.logger.warn('WebSocket server not available for analytics event');
      return;
    }

    switch (type) {
      case 'expo.booth.analytics.update':
        // Emit to booth staff room
        const boothStaffRoom = `booth-staff:${boothId}`;
        server.to(boothStaffRoom).emit('expo.booth.analytics.update', {
          boothId,
          sponsorId,
          stats,
          timestamp: payload.timestamp,
        });
        this.logger.debug(`Emitted analytics update to ${boothStaffRoom}`);

        // Also emit to booth room for attendee-facing metrics if needed
        const boothRoom = `booth:${boothId}`;
        server.to(boothRoom).emit('expo.booth.analytics.update', {
          boothId,
          visitorCount: stats?.currentVisitors,
          timestamp: payload.timestamp,
        });
        break;

      default:
        this.logger.warn(`Unknown analytics event type: ${type}`);
    }
  }
}
