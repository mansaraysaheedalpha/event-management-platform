//src/networking/analytics/analytics.controller.ts
import { Controller, Get, Param, UseGuards, Req } from '@nestjs/common';
import { JwtAuthGuard } from 'src/common/guards/jwt-auth.guard';
import { NetworkingAnalyticsService } from './analytics.service';

interface AuthenticatedRequest extends Request {
  user: { sub: string; email: string };
}

@Controller('analytics')
export class NetworkingAnalyticsController {
  constructor(private readonly analyticsService: NetworkingAnalyticsService) {}

  /**
   * Get comprehensive networking analytics for an event.
   * For organizers to view event performance.
   */
  @UseGuards(JwtAuthGuard)
  @Get('event/:eventId')
  async getEventAnalytics(@Param('eventId') eventId: string) {
    return this.analyticsService.getEventAnalytics(eventId);
  }

  /**
   * Get connection network graph data for visualization.
   */
  @UseGuards(JwtAuthGuard)
  @Get('event/:eventId/graph')
  async getConnectionGraph(@Param('eventId') eventId: string) {
    return this.analyticsService.getConnectionGraph(eventId);
  }

  /**
   * Get outcome breakdown for an event.
   */
  @UseGuards(JwtAuthGuard)
  @Get('event/:eventId/outcomes')
  async getOutcomeBreakdown(@Param('eventId') eventId: string) {
    return this.analyticsService.getOutcomeBreakdown(eventId);
  }

  /**
   * Get networking analytics for the current user.
   */
  @UseGuards(JwtAuthGuard)
  @Get('user/me')
  async getMyAnalytics(@Req() req: AuthenticatedRequest) {
    return this.analyticsService.getUserAnalytics(req.user.sub);
  }

  /**
   * Get networking analytics for a specific user.
   */
  @UseGuards(JwtAuthGuard)
  @Get('user/:userId')
  async getUserAnalytics(@Param('userId') userId: string) {
    return this.analyticsService.getUserAnalytics(userId);
  }
}
