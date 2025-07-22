import { HttpService } from '@nestjs/axios';
import { Inject, Injectable, Logger, forwardRef } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { firstValueFrom } from 'rxjs';
import { MonetizationGateway } from './monetization.gateway';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { AdContent } from 'src/common/interfaces/ad-content.interface';
import { OfferContent } from 'src/common/interfaces/offer-content.interface';
import { WaitlistService } from '../waitlist/waitlist.service';

// Add the Waitlist Offer to our DTOs
interface WaitlistOfferDto {
  title: string;
  message: string;
  join_token: string; // A special, single-use token to claim the spot
  expires_at: string;
}

type MonetizationEventPayload =
  | { type: 'AD_INJECTION'; eventId: string; adId: string }
  | { type: 'UPSELL_OPPORTUNITY'; targetUserId: string; offerId: string }
  | { type: 'SPOT_AVAILABLE'; sessionId: string };

@Injectable()
export class MonetizationService {
  private readonly logger = new Logger(MonetizationService.name);

  constructor(
    private readonly httpService: HttpService,
    @Inject(forwardRef(() => MonetizationGateway))
    private readonly monetizationGateway: MonetizationGateway,
    private readonly waitlistService: WaitlistService,
  ) {}

  @OnEvent('monetization-events')
  async handleMonetizationEvent(payload: MonetizationEventPayload) {
    switch (payload.type) {
      case 'AD_INJECTION': {
        this.logger.log(
          `Processing ad injection for event: ${payload.eventId}`,
        );
        const adContent = await this._fetchAdContent(payload.adId);
        if (adContent) {
          this.monetizationGateway.broadcastAd(adContent);
        }
        break;
      }

      case 'UPSELL_OPPORTUNITY': {
        this.logger.log(`Processing upsell for user: ${payload.targetUserId}`);
        const offerContent = await this._fetchOfferContent(payload.offerId);
        if (offerContent) {
          this.monetizationGateway.sendUpsellToUser(
            payload.targetUserId,
            offerContent,
          );
        }
        break;
      }

      case 'SPOT_AVAILABLE': {
        this.logger.log(`Spot available in session: ${payload.sessionId}`);
        const nextUserId = await this.waitlistService.getNextUserFromWaitlist(
          payload.sessionId,
        );
        if (nextUserId) {
          // In a real system, you might fetch a special offer or token here
          const notificationPayload = await this._fetchWaitlistOffer(
            payload.sessionId,
          );
          if (notificationPayload) {
            this.monetizationGateway.sendWaitlistNotification(
              nextUserId,
              notificationPayload,
            );
          }
        }
        break;
      }
    }
  }

  // NEW: Method to fetch the waitlist offer from the Event Lifecycle service
  private async _fetchWaitlistOffer(
    sessionId: string,
  ): Promise<WaitlistOfferDto | null> {
    try {
      const eventServiceUrl =
        process.env.EVENT_SERVICE_URL || 'http://localhost:8000';
      const response = await firstValueFrom(
        this.httpService.get<WaitlistOfferDto>(
          `${eventServiceUrl}/internal/sessions/${sessionId}/waitlist-offer`,
          {
            headers: { 'X-Internal-Api-Key': process.env.INTERNAL_API_KEY },
          },
        ),
      );
      return response.data;
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(
        `Failed to fetch waitlist offer for session ${sessionId}: ${errorMessage}`,
      );
      return null;
    }
  }


  private async _fetchAdContent(adId: string): Promise<AdContent | null> {
    try {
      const eventServiceUrl =
        process.env.EVENT_SERVICE_URL || 'http://localhost:8000';
      const response = await firstValueFrom(
        this.httpService.get<AdContent>(
          `${eventServiceUrl}/internal/ads/${adId}`,
          {
            headers: { 'X-Internal-Api-Key': process.env.INTERNAL_API_KEY },
          },
        ),
      );
      return response.data;
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(
        `Failed to fetch ad content for ad ${adId}: ${errorMessage}`,
      );
      return null;
    }
  }

  // NEW: Method to fetch offer details from the Event Lifecycle service
  private async _fetchOfferContent(
    offerId: string,
  ): Promise<OfferContent | null> {
    try {
      const eventServiceUrl =
        process.env.EVENT_SERVICE_URL || 'http://localhost:8000';
      const response = await firstValueFrom(
        this.httpService.get<OfferContent>(
          `${eventServiceUrl}/internal/offers/${offerId}`,
          {
            headers: { 'X-Internal-Api-Key': process.env.INTERNAL_API_KEY },
          },
        ),
      );
      return response.data;
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      this.logger.error(
        `Failed to fetch offer content for offer ${offerId}: ${errorMessage}`,
      );
      return null;
    }
  }
}
