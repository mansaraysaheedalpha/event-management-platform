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
import { ExpoAnalyticsService, LeadFormData } from './expo-analytics.service';

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

interface SyncBoothStaffPayload {
  sponsorId: string;
  userId: string;
  action: 'add' | 'remove';
}

interface BulkSyncBoothStaffPayload {
  sponsorId: string;
  userIds: string[];
}

@Controller('internal/expo')
@UseGuards(InternalApiKeyGuard)
export class ExpoInternalController {
  private readonly logger = new Logger(ExpoInternalController.name);

  constructor(
    private readonly expoService: ExpoService,
    private readonly analyticsService: ExpoAnalyticsService,
  ) {}

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

  /**
   * Sync booth staff when a sponsor representative is added or removed.
   * Called by event-lifecycle-service when a user accepts an invitation
   * or is removed from a sponsor.
   */
  @Post('booth-staff')
  @HttpCode(HttpStatus.OK)
  async syncBoothStaff(@Body() payload: SyncBoothStaffPayload) {
    this.logger.log(
      `Received booth staff sync request: ${payload.action} user ${payload.userId} for sponsor ${payload.sponsorId}`,
    );

    try {
      // Find booth by sponsor ID
      const booth = await this.expoService.getBoothBySponsorId(payload.sponsorId);

      if (!booth) {
        this.logger.log(
          `No booth exists for sponsor ${payload.sponsorId}. Staff sync skipped.`,
        );
        return {
          success: true,
          staffSynced: false,
          reason: 'NO_BOOTH',
          message: 'No booth exists for this sponsor.',
        };
      }

      if (payload.action === 'add') {
        // Check if user is already in staffIds
        const staffIds = booth.staffIds || [];
        if (staffIds.includes(payload.userId)) {
          return {
            success: true,
            staffSynced: false,
            reason: 'ALREADY_STAFF',
            message: 'User is already booth staff.',
          };
        }

        await this.expoService.addBoothStaff(booth.id, payload.userId);
        this.logger.log(
          `Added user ${payload.userId} as staff for booth ${booth.id}`,
        );

        return {
          success: true,
          staffSynced: true,
          boothId: booth.id,
          action: 'added',
        };
      } else if (payload.action === 'remove') {
        // Check if user is in staffIds
        const staffIds = booth.staffIds || [];
        if (!staffIds.includes(payload.userId)) {
          return {
            success: true,
            staffSynced: false,
            reason: 'NOT_STAFF',
            message: 'User is not booth staff.',
          };
        }

        await this.expoService.removeBoothStaff(booth.id, payload.userId);
        this.logger.log(
          `Removed user ${payload.userId} from staff for booth ${booth.id}`,
        );

        return {
          success: true,
          staffSynced: true,
          boothId: booth.id,
          action: 'removed',
        };
      }

      return {
        success: false,
        reason: 'INVALID_ACTION',
        message: 'Action must be "add" or "remove".',
      };
    } catch (error) {
      this.logger.error(
        `Failed to sync booth staff for sponsor ${payload.sponsorId}: ${error.message}`,
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
   * Bulk sync all sponsor representatives to booth staff.
   * Used to repair existing sponsor reps who were added before
   * the automatic booth staff sync was implemented.
   */
  @Post('booth-staff/bulk')
  @HttpCode(HttpStatus.OK)
  async bulkSyncBoothStaff(@Body() payload: BulkSyncBoothStaffPayload) {
    this.logger.log(
      `Received bulk booth staff sync request for sponsor ${payload.sponsorId} with ${payload.userIds.length} users`,
    );

    try {
      // Find booth by sponsor ID
      const booth = await this.expoService.getBoothBySponsorId(payload.sponsorId);

      if (!booth) {
        this.logger.log(
          `No booth exists for sponsor ${payload.sponsorId}. Bulk sync skipped.`,
        );
        return {
          success: true,
          staffSynced: false,
          reason: 'NO_BOOTH',
          message: 'No booth exists for this sponsor.',
        };
      }

      const currentStaffIds = booth.staffIds || [];
      const usersToAdd = payload.userIds.filter(
        (userId) => !currentStaffIds.includes(userId),
      );

      if (usersToAdd.length === 0) {
        return {
          success: true,
          staffSynced: false,
          reason: 'ALL_ALREADY_STAFF',
          message: 'All users are already booth staff.',
        };
      }

      // Add all users
      for (const userId of usersToAdd) {
        await this.expoService.addBoothStaff(booth.id, userId);
      }

      this.logger.log(
        `Bulk synced ${usersToAdd.length} users as staff for booth ${booth.id}`,
      );

      return {
        success: true,
        staffSynced: true,
        boothId: booth.id,
        usersAdded: usersToAdd.length,
        usersSkipped: payload.userIds.length - usersToAdd.length,
      };
    } catch (error) {
      this.logger.error(
        `Failed to bulk sync booth staff for sponsor ${payload.sponsorId}: ${error.message}`,
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
   * Resync all booth leads to event-lifecycle-service.
   * This fixes leads that failed to sync during capture.
   * Accepts either boothId or sponsorId to identify the booth.
   */
  @Post('booth-leads/resync')
  @HttpCode(HttpStatus.OK)
  async resyncBoothLeads(@Body() payload: { boothId?: string; sponsorId?: string }) {
    this.logger.log(
      `Received resync request for booth ${payload.boothId || 'by sponsor ' + payload.sponsorId} leads`,
    );

    try {
      // Get booth by boothId or sponsorId
      let booth;
      if (payload.boothId) {
        booth = await this.expoService.getBooth(payload.boothId);
      } else if (payload.sponsorId) {
        booth = await this.expoService.getBoothBySponsorId(payload.sponsorId);
      } else {
        throw new HttpException(
          { success: false, error: 'Either boothId or sponsorId is required' },
          HttpStatus.BAD_REQUEST,
        );
      }

      if (!booth) {
        throw new HttpException(
          { success: false, error: 'Booth not found' },
          HttpStatus.NOT_FOUND,
        );
      }

      const boothId = booth.id;

      // Get all leads for this booth
      const leads = await this.analyticsService.getRecentLeads(
        boothId,
        1000, // Get all leads (max 1000)
      );

      this.logger.log(`Found ${leads.length} leads to resync for booth ${boothId}`);

      const results: Array<{
        visitorId: string;
        success: boolean;
        error?: string;
      }> = [];
      let syncedCount = 0;
      let failedCount = 0;

      // Resync each lead
      for (const lead of leads) {
        try {
          await this.analyticsService.syncLeadToEventService(
            lead.visitorId,
            boothId,
            lead.formData as LeadFormData,
          );
          syncedCount++;
          results.push({
            visitorId: lead.visitorId,
            success: true,
          });
        } catch (error) {
          failedCount++;
          results.push({
            visitorId: lead.visitorId,
            success: false,
            error: error.message,
          });
          this.logger.warn(
            `Failed to resync lead ${lead.visitorId}: ${error.message}`,
          );
        }
      }

      this.logger.log(
        `Resync complete for booth ${boothId}: ${syncedCount} synced, ${failedCount} failed`,
      );

      return {
        success: true,
        boothId,
        boothName: booth.name,
        summary: {
          total: leads.length,
          synced: syncedCount,
          failed: failedCount,
        },
        results,
      };
    } catch (error) {
      this.logger.error(
        `Failed to resync booth leads: ${error.message}`,
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
}
