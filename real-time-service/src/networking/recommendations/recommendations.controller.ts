//src/networking/recommendations/recommendations.controller.ts
import {
  Controller,
  Get,
  Post,
  Param,
  Query,
  UseGuards,
  Req,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { Throttle } from '@nestjs/throttler';
import { RecommendationsService } from './recommendations.service';
import {
  GetRecommendationsDto,
  RecommendationsResponseDto,
} from './dto';
import { RolesGuard, RestThrottlerGuard } from 'src/common/guards';
import { Roles } from 'src/common/decorators';

interface AuthenticatedRequest {
  user: {
    sub: string;
    email: string;
    orgId?: string;
  };
}

/**
 * Recommendations Controller
 *
 * Provides REST endpoints for AI-powered attendee matchmaking.
 * All endpoints require JWT authentication and rate limiting.
 *
 * SECURITY:
 * - Users can only access their own recommendations
 * - Sensitive data (email/phone) is never exposed in responses
 * - Rate limiting prevents abuse (100 req/min default, 1 req/2s for refresh)
 */
@Controller('events/:eventId/recommendations')
@UseGuards(RestThrottlerGuard)
export class RecommendationsController {
  constructor(private readonly recommendationsService: RecommendationsService) {}

  /**
   * Get personalized recommendations for the authenticated user.
   *
   * @param eventId - The event ID
   * @param query - Optional filtering and pagination params
   * @param req - Authenticated request with user info
   * @returns Paginated list of recommendations with user display info
   */
  @UseGuards(AuthGuard('jwt'))
  @Get()
  async getMyRecommendations(
    @Param('eventId') eventId: string,
    @Query() query: GetRecommendationsDto,
    @Req() req: AuthenticatedRequest,
  ): Promise<RecommendationsResponseDto> {
    const userId = req.user.sub;

    return this.recommendationsService.getRecommendations(userId, eventId, {
      limit: query.limit,
      refresh: query.refresh,
    });
  }

  /**
   * Force refresh recommendations for the authenticated user.
   * This triggers a new LLM call to oracle-ai-service.
   *
   * Strictly rate limited: 1 request per 2 seconds to prevent abuse.
   * Frontend also enforces 2-second debounce.
   */
  @UseGuards(AuthGuard('jwt'))
  @Throttle({ default: { ttl: 2000, limit: 1 } })
  @Post('refresh')
  @HttpCode(HttpStatus.OK)
  async refreshRecommendations(
    @Param('eventId') eventId: string,
    @Req() req: AuthenticatedRequest,
  ): Promise<RecommendationsResponseDto> {
    const userId = req.user.sub;

    return this.recommendationsService.getRecommendations(userId, eventId, {
      refresh: true,
    });
  }

  /**
   * Track when a recommendation is viewed.
   * Used for analytics and recommendation quality improvement.
   */
  @UseGuards(AuthGuard('jwt'))
  @Post(':recommendationId/viewed')
  @HttpCode(HttpStatus.NO_CONTENT)
  async markViewed(
    @Param('eventId') eventId: string,
    @Param('recommendationId') recommendationId: string,
    @Req() req: AuthenticatedRequest,
  ): Promise<void> {
    const userId = req.user.sub;
    await this.recommendationsService.markViewed(recommendationId, userId, eventId);
  }

  /**
   * Track when a recommended user is pinged.
   * Used for analytics and recommendation quality improvement.
   */
  @UseGuards(AuthGuard('jwt'))
  @Post(':recommendationId/pinged')
  @HttpCode(HttpStatus.NO_CONTENT)
  async markPinged(
    @Param('eventId') eventId: string,
    @Param('recommendationId') recommendationId: string,
    @Req() req: AuthenticatedRequest,
  ): Promise<void> {
    const userId = req.user.sub;
    await this.recommendationsService.markPinged(recommendationId, userId, eventId);
  }

  /**
   * Track when a recommendation led to a connection.
   * Called automatically when user connects via recommendation card.
   */
  @UseGuards(AuthGuard('jwt'))
  @Post(':recommendationId/connected')
  @HttpCode(HttpStatus.NO_CONTENT)
  async markConnected(
    @Param('eventId') eventId: string,
    @Param('recommendationId') recommendationId: string,
    @Req() req: AuthenticatedRequest,
  ): Promise<void> {
    const userId = req.user.sub;
    await this.recommendationsService.markConnected(recommendationId, userId, eventId);
  }

  /**
   * Get recommendation analytics for an event.
   * Admin-only endpoint for organizers to see recommendation performance.
   *
   * Requires one of:
   * - Role: admin, owner, organizer
   * - Permission: analytics:view, event:manage
   */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('admin', 'owner', 'organizer', 'analytics:view', 'event:manage')
  @Get('analytics')
  async getAnalytics(
    @Param('eventId') eventId: string,
  ): Promise<{
    totalRecommendations: number;
    viewedCount: number;
    viewRate: number;
    pingedCount: number;
    pingRate: number;
    connectedCount: number;
    connectionRate: number;
    averageMatchScore: number;
  }> {
    return this.recommendationsService.getRecommendationAnalytics(eventId);
  }
}
