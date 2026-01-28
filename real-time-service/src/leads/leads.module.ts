// src/leads/leads.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { LeadEventsConsumer } from './lead-events.consumer';
import { LeadStatsCacheService } from './lead-stats-cache.service';
import { LeadBroadcastService } from './lead-broadcast.service';
import { LeadsListener } from './leads.listener';
import { SharedModule } from '../shared/shared.module';
import { SponsorsModule } from '../monetization/sponsors/sponsors.module';

/**
 * LeadsModule - Real-time lead metrics infrastructure.
 *
 * This module provides:
 * - Redis Streams consumer for guaranteed delivery of lead events
 * - Redis-based caching for lead statistics
 * - Pub/Sub broadcast service for multi-instance WebSocket support
 * - Listener that bridges Pub/Sub to Socket.IO
 *
 * Architecture:
 * ```
 * Kafka (lead.capture.events.v1)
 *   ↓
 * event-lifecycle-service (creates SponsorLead)
 *   ↓
 * Redis Stream (platform.leads.events.v1)
 *   ↓
 * LeadEventsConsumer (this module)
 *   ├→ LeadStatsCacheService (update counters)
 *   └→ LeadBroadcastService (publish to Pub/Sub)
 *        ↓
 *      Redis Pub/Sub (lead-events channel)
 *        ↓
 *      LeadsListener (subscribe & emit WebSocket)
 *        ↓
 *      Socket.IO → Frontend
 * ```
 */
@Module({
  imports: [
    ConfigModule,
    SharedModule,
    // Use forwardRef to handle circular dependency with SponsorsModule
    forwardRef(() => SponsorsModule),
  ],
  providers: [
    LeadEventsConsumer,
    LeadStatsCacheService,
    LeadBroadcastService,
    LeadsListener,
  ],
  exports: [
    LeadStatsCacheService,
    LeadBroadcastService,
  ],
})
export class LeadsModule {}
