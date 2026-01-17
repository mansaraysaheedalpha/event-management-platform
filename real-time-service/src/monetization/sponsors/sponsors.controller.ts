//src/monetization/sponsors/sponsors.controller.ts
import {
  Controller,
  Post,
  Body,
  UseGuards,
  Logger,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { EventEmitter2 } from '@nestjs/event-emitter';
import { InternalApiKeyGuard } from '../../common/guards/internal-api-key.guard';

interface LeadEventPayload {
  eventType: 'LEAD_CAPTURED' | 'LEAD_INTENT_UPDATE';
  sponsorId: string;
  data: {
    id?: string;
    leadId?: string;
    userId?: string;
    userName?: string;
    userEmail?: string;
    userCompany?: string;
    userTitle?: string;
    intentScore?: number;
    intentLevel?: string;
    interactionType?: string;
    interactionCount?: number;
    capturedAt?: string;
  };
}

@Controller('internal/sponsors')
@UseGuards(InternalApiKeyGuard)
export class SponsorsController {
  private readonly logger = new Logger(SponsorsController.name);

  constructor(private readonly eventEmitter: EventEmitter2) {}

  /**
   * Receive lead events from event-lifecycle-service and emit them internally
   * for WebSocket broadcast to connected sponsor dashboards.
   */
  @Post('lead-event')
  @HttpCode(HttpStatus.OK)
  async handleLeadEvent(@Body() payload: LeadEventPayload) {
    this.logger.log(
      `Received ${payload.eventType} event for sponsor ${payload.sponsorId}`,
    );

    if (payload.eventType === 'LEAD_CAPTURED') {
      // Emit event for SponsorsService to broadcast via WebSocket
      this.eventEmitter.emit('monetization-events', {
        type: 'LEAD_CAPTURED',
        sponsorId: payload.sponsorId,
        leadData: {
          id: payload.data.id,
          user: {
            id: payload.data.userId,
            name: payload.data.userName,
            email: payload.data.userEmail,
            company: payload.data.userCompany,
            title: payload.data.userTitle,
          },
          intentScore: payload.data.intentScore,
          intentLevel: payload.data.intentLevel,
          action: payload.data.interactionType,
          timestamp: payload.data.capturedAt,
        },
      });
    } else if (payload.eventType === 'LEAD_INTENT_UPDATE') {
      this.eventEmitter.emit('monetization-events', {
        type: 'LEAD_INTENT_UPDATE',
        sponsorId: payload.sponsorId,
        leadUserId: payload.data.userId || payload.data.leadId,
        intentScore: payload.data.intentScore,
        latestAction: payload.data.interactionType,
      });
    }

    return { success: true };
  }
}
