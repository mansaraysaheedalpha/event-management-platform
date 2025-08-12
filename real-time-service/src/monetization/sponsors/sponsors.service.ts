//src/monetization/sponsors/sponsors.service.ts
import { Inject, Injectable, Logger, forwardRef } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { SponsorsGateway } from './sponsors.gateway';

// Define the shape of the incoming lead event
interface LeadCapturedPayload {
  type: 'LEAD_CAPTURED';
  sponsorId: string;
  leadData: {
    user: { id: string; name: string };
    action: string; // e.g., 'CONTENT_DOWNLOADED'
    timestamp: string;
  };
}

// Define the shape of the new intent update event
interface LeadIntentUpdatePayload {
  type: 'LEAD_INTENT_UPDATE';
  sponsorId: string;
  leadUserId: string;
  intentScore: number;
  latestAction: string;
}

// Update our main payload type to include the new event
type SponsorEventPayload = LeadCapturedPayload | LeadIntentUpdatePayload;

@Injectable()
export class SponsorsService {
  private readonly logger = new Logger(SponsorsService.name);

  constructor(
    @Inject(forwardRef(() => SponsorsGateway))
    private readonly sponsorsGateway: SponsorsGateway,
  ) {}
  @OnEvent('monetization-events') // This listener now handles multiple event types
  handleMonetizationEvent(payload: SponsorEventPayload) {
    switch (payload.type) {
      case 'LEAD_CAPTURED':
        this.logger.log(
          `Processing new lead for sponsor: ${payload.sponsorId}`,
        );
        this.sponsorsGateway.broadcastNewLead(
          payload.sponsorId,
          payload.leadData,
        );
        break;

      // --- NEW LOGIC ---
      case 'LEAD_INTENT_UPDATE':
        this.logger.log(
          `Processing lead intent update for sponsor: ${payload.sponsorId}`,
        );
        this.sponsorsGateway.broadcastLeadIntentUpdate(payload.sponsorId, {
          leadUserId: payload.leadUserId,
          intentScore: payload.intentScore,
          latestAction: payload.latestAction,
        });
        break;
      // --- END OF NEW LOGIC ---
    }
  }
}
