//src/networking/recommendations/feedback.controller.ts
import {
  Controller,
  Get,
  Post,
  Param,
  Body,
  UseGuards,
  Req,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { FeedbackService } from './feedback.service';
import { SubmitConnectionFeedbackDto, SubmitRecommendationFeedbackDto } from './dto';
import { RolesGuard } from 'src/common/guards';
import { Roles } from 'src/common/decorators';

interface AuthenticatedRequest {
  user: {
    sub: string;
    email: string;
    orgId?: string;
  };
}

/**
 * Feedback Controller
 *
 * Handles collection and retrieval of feedback on connections
 * and recommendations. Used to improve the AI matchmaking system.
 *
 * All endpoints require JWT authentication.
 */
@Controller('events/:eventId/feedback')
export class FeedbackController {
  constructor(private readonly feedbackService: FeedbackService) {}

  /**
   * Submit feedback for a connection
   */
  @UseGuards(AuthGuard('jwt'))
  @Post('connections')
  @HttpCode(HttpStatus.CREATED)
  async submitConnectionFeedback(
    @Param('eventId') eventId: string,
    @Body() dto: SubmitConnectionFeedbackDto,
    @Req() req: AuthenticatedRequest,
  ): Promise<{ success: true }> {
    const userId = req.user.sub;

    await this.feedbackService.submitConnectionFeedback(userId, {
      connectionId: dto.connectionId,
      rating: dto.rating,
      wasValuable: dto.wasValuable,
      willFollowUp: dto.willFollowUp,
      wouldRecommend: dto.wouldRecommend,
      positiveFactors: dto.positiveFactors,
      negativeFactors: dto.negativeFactors,
      comments: dto.comments,
    });

    return { success: true };
  }

  /**
   * Submit feedback for a recommendation action
   */
  @UseGuards(AuthGuard('jwt'))
  @Post('recommendations')
  @HttpCode(HttpStatus.CREATED)
  async submitRecommendationFeedback(
    @Param('eventId') eventId: string,
    @Body() dto: SubmitRecommendationFeedbackDto,
    @Req() req: AuthenticatedRequest,
  ): Promise<{ success: true }> {
    const userId = req.user.sub;

    await this.feedbackService.submitRecommendationFeedback(userId, {
      recommendationId: dto.recommendationId,
      action: dto.action,
      connectionRating: dto.connectionRating,
      skipReason: dto.skipReason,
    });

    return { success: true };
  }

  /**
   * Get feedback status for the authenticated user
   * Returns pending connections that need feedback
   */
  @UseGuards(AuthGuard('jwt'))
  @Get('status')
  async getFeedbackStatus(
    @Param('eventId') eventId: string,
    @Req() req: AuthenticatedRequest,
  ): Promise<{
    totalConnections: number;
    feedbackGiven: number;
    pendingConnections: Array<{
      connectionId: string;
      otherUserName: string;
      connectedAt: Date;
    }>;
  }> {
    const userId = req.user.sub;
    return this.feedbackService.getUserFeedbackStatus(userId, eventId);
  }

  /**
   * Get aggregated feedback analytics for an event.
   * Admin-only endpoint for organizers to see feedback trends.
   *
   * Requires one of:
   * - Role: admin, owner, organizer
   * - Permission: analytics:view, event:manage
   */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('admin', 'owner', 'organizer', 'analytics:view', 'event:manage')
  @Get('analytics')
  async getFeedbackAnalytics(
    @Param('eventId') eventId: string,
  ): Promise<{
    averageRating: number;
    totalFeedback: number;
    positiveCount: number;
    negativeCount: number;
    topPositiveFactors: Array<{ factor: string; count: number }>;
    topNegativeFactors: Array<{ factor: string; count: number }>;
    followUpRate: number;
    recommendRate: number;
  }> {
    return this.feedbackService.getEventFeedbackAggregation(eventId);
  }
}
