import { Controller, Get, Logger, Query, UseGuards } from '@nestjs/common';
import { EventPattern, Payload } from '@nestjs/microservices';
import { DashboardService, EngagementBreakdownData } from './dashboard.service';
import { InternalApiKeyGuard } from 'src/common/guards/internal-api-key.guard';

@Controller('internal/dashboard')
export class DashboardController {
  private readonly logger = new Logger(DashboardController.name);

  constructor(private readonly dashboardService: DashboardService) {}

  @EventPattern('platform.analytics.check-in.v1')
  async handleCheckInEvent(@Payload() data: any) {
    this.logger.log(
      `Received check-in event from Kafka: ${JSON.stringify(data)}`,
    );
    await this.dashboardService.handleAnalyticsEvent(data);
  }

  /**
   * Internal API endpoint for fetching engagement breakdown data.
   * Protected by internal API key - only accessible by other services.
   *
   * @param eventId - Optional event ID to scope metrics
   * @param orgId - Organization ID (required if no eventId)
   * @param totalAttendees - Total attendees for rate calculations
   */
  @Get('engagement-breakdown')
  @UseGuards(InternalApiKeyGuard)
  async getEngagementBreakdown(
    @Query('eventId') eventId?: string,
    @Query('orgId') orgId?: string,
    @Query('totalAttendees') totalAttendeesStr?: string,
  ): Promise<EngagementBreakdownData> {
    // Clamp totalAttendees to [0, 1_000_000] to prevent abuse via extreme values
    const totalAttendees = totalAttendeesStr
      ? Math.max(0, Math.min(parseInt(totalAttendeesStr, 10) || 0, 1_000_000))
      : 0;

    this.logger.log(
      `Fetching engagement breakdown - eventId: ${eventId}, orgId: ${orgId}, totalAttendees: ${totalAttendees}`,
    );

    return this.dashboardService.getEngagementBreakdown(
      eventId,
      orgId,
      totalAttendees,
    );
  }

  /**
   * Internal API endpoint for fetching dashboard data for an event.
   * Protected by internal API key.
   *
   * @param eventId - Event ID to fetch dashboard data for
   */
  @Get('data')
  @UseGuards(InternalApiKeyGuard)
  async getDashboardData(@Query('eventId') eventId: string) {
    this.logger.log(`Fetching dashboard data for event: ${eventId}`);
    return this.dashboardService.getDashboardData(eventId);
  }
}
