// src/expo/expo-internal.controller.ts
import {
  Controller,
  Post,
  Body,
  UseGuards,
  Logger,
  HttpCode,
  HttpStatus,
  HttpException,
} from '@nestjs/common';
import { InternalApiKeyGuard } from '../common/guards/internal-api-key.guard';
import { ExpoService } from './expo.service';

interface CreateBoothForSponsorPayload {
  eventId: string;
  sponsorId: string;
  organizationId: string;
  companyName: string;
  companyDescription?: string;
  companyLogoUrl?: string;
  tier?: 'PLATINUM' | 'GOLD' | 'SILVER' | 'BRONZE' | 'STARTUP';
  boothNumber?: string;
  category?: string;
}

interface SponsorUpdatedPayload {
  eventId: string;
  sponsorId: string;
  organizationId: string;
  companyName?: string;
  companyDescription?: string;
  companyLogoUrl?: string;
  tier?: 'PLATINUM' | 'GOLD' | 'SILVER' | 'BRONZE' | 'STARTUP';
  category?: string;
}

interface SponsorArchivedPayload {
  eventId: string;
  sponsorId: string;
}

@Controller('internal/expo')
@UseGuards(InternalApiKeyGuard)
export class ExpoInternalController {
  private readonly logger = new Logger(ExpoInternalController.name);

  constructor(private readonly expoService: ExpoService) {}

  /**
   * Automatically creates a booth when a sponsor is added to an event.
   * Called by event-lifecycle-service after sponsor creation.
   *
   * If no expo hall exists for the event, does nothing (booth will be created
   * when expo hall is set up, or manually by organizer).
   */
  @Post('sponsor-booth')
  @HttpCode(HttpStatus.CREATED)
  async createBoothForSponsor(@Body() payload: CreateBoothForSponsorPayload) {
    this.logger.log(
      `Received booth creation request for sponsor ${payload.sponsorId} in event ${payload.eventId}`,
    );

    try {
      // Check if expo hall exists for this event
      const hall = await this.expoService.getExpoHallSafe(payload.eventId);

      if (!hall) {
        this.logger.log(
          `No expo hall exists for event ${payload.eventId}. Booth will not be auto-created.`,
        );
        return {
          success: true,
          boothCreated: false,
          reason: 'NO_EXPO_HALL',
          message:
            'No expo hall exists for this event. Booth can be created manually later.',
        };
      }

      // Check if booth already exists for this sponsor
      const existingBooth = await this.expoService.getBoothBySponsorId(
        payload.sponsorId,
      );
      if (existingBooth) {
        this.logger.log(
          `Booth already exists for sponsor ${payload.sponsorId}`,
        );
        return {
          success: true,
          boothCreated: false,
          reason: 'BOOTH_EXISTS',
          booth: existingBooth,
        };
      }

      // Create booth for sponsor
      const booth = await this.expoService.createBooth(
        hall.id,
        payload.organizationId,
        {
          name: payload.companyName,
          description: payload.companyDescription,
          logoUrl: payload.companyLogoUrl,
          tier: payload.tier,
          sponsorId: payload.sponsorId,
          category: payload.category,
        },
      );

      this.logger.log(
        `Auto-created booth ${booth.id} for sponsor ${payload.sponsorId}`,
      );

      return {
        success: true,
        boothCreated: true,
        booth,
      };
    } catch (error) {
      this.logger.error(
        `Failed to create booth for sponsor ${payload.sponsorId}: ${error.message}`,
      );
      throw new HttpException(
        {
          success: false,
          error: error.message,
        },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }

  /**
   * Updates a booth when sponsor details are updated.
   * Called by event-lifecycle-service after sponsor update.
   */
  @Post('sponsor-booth/update')
  @HttpCode(HttpStatus.OK)
  async updateBoothForSponsor(@Body() payload: SponsorUpdatedPayload) {
    this.logger.log(
      `Received booth update request for sponsor ${payload.sponsorId}`,
    );

    try {
      // Find booth by sponsor ID
      const existingBooth = await this.expoService.getBoothBySponsorId(
        payload.sponsorId,
      );

      if (!existingBooth) {
        this.logger.log(
          `No booth exists for sponsor ${payload.sponsorId}. Nothing to update.`,
        );
        return {
          success: true,
          boothUpdated: false,
          reason: 'NO_BOOTH',
        };
      }

      // Update booth with sponsor's updated information
      // Note: Booths don't have isActive - sponsor deactivation is handled via deactivate endpoint
      const updateData: Record<string, unknown> = {};

      if (payload.companyName !== undefined) {
        updateData.name = payload.companyName;
      }
      if (payload.companyDescription !== undefined) {
        updateData.description = payload.companyDescription;
      }
      if (payload.companyLogoUrl !== undefined) {
        updateData.logoUrl = payload.companyLogoUrl;
      }
      if (payload.tier !== undefined) {
        updateData.tier = payload.tier;
      }
      if (payload.category !== undefined) {
        updateData.category = payload.category;
      }

      if (Object.keys(updateData).length === 0) {
        return {
          success: true,
          boothUpdated: false,
          reason: 'NO_CHANGES',
        };
      }

      const booth = await this.expoService.updateBooth(
        existingBooth.id,
        updateData,
      );

      this.logger.log(
        `Updated booth ${booth.id} for sponsor ${payload.sponsorId}`,
      );

      return {
        success: true,
        boothUpdated: true,
        booth,
      };
    } catch (error) {
      this.logger.error(
        `Failed to update booth for sponsor ${payload.sponsorId}: ${error.message}`,
      );
      throw new HttpException(
        {
          success: false,
          error: error.message,
        },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }

  /**
   * Removes a booth when a sponsor is archived/deleted.
   * Called by event-lifecycle-service after sponsor archival.
   *
   * Note: Since booths don't have an isActive field, we delete the booth
   * when the sponsor is archived. This is a hard delete.
   */
  @Post('sponsor-booth/deactivate')
  @HttpCode(HttpStatus.OK)
  async deactivateBoothForSponsor(@Body() payload: SponsorArchivedPayload) {
    this.logger.log(
      `Received booth removal request for archived sponsor ${payload.sponsorId}`,
    );

    try {
      const existingBooth = await this.expoService.getBoothBySponsorId(
        payload.sponsorId,
      );

      if (!existingBooth) {
        return {
          success: true,
          boothDeactivated: false,
          reason: 'NO_BOOTH',
        };
      }

      // Delete the booth since booths don't have an isActive field
      await this.expoService.deleteBooth(existingBooth.id);

      this.logger.log(
        `Removed booth ${existingBooth.id} for archived sponsor ${payload.sponsorId}`,
      );

      return {
        success: true,
        boothDeactivated: true,
        boothId: existingBooth.id,
      };
    } catch (error) {
      this.logger.error(
        `Failed to remove booth for sponsor ${payload.sponsorId}: ${error.message}`,
      );
      throw new HttpException(
        {
          success: false,
          error: error.message,
        },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }

  /**
   * Creates booths for all existing sponsors when an expo hall is created.
   * Called by event-lifecycle-service or can be triggered manually.
   */
  @Post('sync-sponsors')
  @HttpCode(HttpStatus.OK)
  async syncSponsorsToBooths(
    @Body()
    payload: {
      eventId: string;
      sponsors: CreateBoothForSponsorPayload[];
    },
  ) {
    this.logger.log(
      `Received sync request for ${payload.sponsors.length} sponsors in event ${payload.eventId}`,
    );

    const results: Array<{
      sponsorId: string;
      success: boolean;
      boothId?: string;
      reason?: string;
    }> = [];

    for (const sponsor of payload.sponsors) {
      try {
        const result = await this.createBoothForSponsor({
          ...sponsor,
          eventId: payload.eventId,
        });

        results.push({
          sponsorId: sponsor.sponsorId,
          success: true,
          boothId: result.booth?.id,
          reason: result.reason,
        });
      } catch (error) {
        results.push({
          sponsorId: sponsor.sponsorId,
          success: false,
          reason: error.message,
        });
      }
    }

    const created = results.filter((r) => r.boothId).length;
    const skipped = results.filter((r) => r.success && !r.boothId).length;
    const failed = results.filter((r) => !r.success).length;

    this.logger.log(
      `Sync complete: ${created} booths created, ${skipped} skipped, ${failed} failed`,
    );

    return {
      success: true,
      summary: { created, skipped, failed },
      results,
    };
  }
}
