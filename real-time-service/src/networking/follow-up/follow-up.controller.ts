//src/networking/follow-up/follow-up.controller.ts
import {
  Controller,
  Get,
  Post,
  Body,
  Param,
  Query,
  UseGuards,
  Req,
  Res,
  HttpStatus,
} from '@nestjs/common';
import { Response } from 'express';
import { Throttle } from '@nestjs/throttler';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { JwtAuthGuard, RestThrottlerGuard } from 'src/common/guards';
import { FollowUpService } from './follow-up.service';
import { ScheduleFollowUpsDto, SendFollowUpDto, GenerateFollowUpDto } from './dto';

// Transparent 1x1 pixel for email tracking
const TRANSPARENT_PIXEL = Buffer.from(
  'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',
  'base64',
);

interface AuthenticatedRequest extends Request {
  user: {
    sub: string;
    email: string;
  };
}

@ApiTags('Follow-Up')
@Controller('follow-up')
@UseGuards(RestThrottlerGuard)
export class FollowUpController {
  constructor(private readonly followUpService: FollowUpService) {}

  /**
   * Schedule follow-up emails for all connections at an event.
   * Typically called by organizer after event ends.
   * Rate limited: 5 requests per minute to prevent spam.
   */
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Schedule follow-up emails for event connections' })
  @Throttle({ default: { ttl: 60000, limit: 5 } })
  @Post('schedule')
  async scheduleFollowUps(@Body() dto: ScheduleFollowUpsDto) {
    const scheduledFor = dto.scheduledFor ? new Date(dto.scheduledFor) : undefined;
    return this.followUpService.scheduleEventFollowUps(dto.eventId, scheduledFor);
  }

  /**
   * Get follow-up email preview for a user at an event.
   */
  @UseGuards(JwtAuthGuard)
  @Get('preview/:eventId')
  async getFollowUpPreview(
    @Param('eventId') eventId: string,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.followUpService.generateFollowUpEmail(req.user.sub, eventId);
  }

  /**
   * Get pending follow-ups for the authenticated user.
   */
  @UseGuards(JwtAuthGuard)
  @Get('pending')
  async getPendingFollowUps(@Req() req: AuthenticatedRequest) {
    return this.followUpService.getPendingFollowUps(req.user.sub);
  }

  /**
   * Generate AI-powered follow-up message suggestion.
   */
  @UseGuards(JwtAuthGuard)
  @Post('generate')
  async generateFollowUpSuggestion(
    @Body() dto: GenerateFollowUpDto,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.followUpService.generateAIFollowUpSuggestion(
      dto.connectionId,
      req.user.sub,
      dto.tone,
      dto.additionalContext,
    );
  }

  /**
   * Send a follow-up message for a specific connection.
   * Rate limited: 10 messages per minute to prevent spam.
   */
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Send follow-up message for a connection' })
  @Throttle({ default: { ttl: 60000, limit: 10 } })
  @Post(':connectionId/send')
  async sendFollowUp(
    @Param('connectionId') connectionId: string,
    @Body() dto: SendFollowUpDto,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.followUpService.sendFollowUpMessage(
      connectionId,
      dto.message,
      req.user.sub,
    );
  }

  /**
   * Track email open via transparent pixel.
   * No auth required - called from email client.
   */
  @Get('track/open/:connectionId')
  async trackOpen(
    @Param('connectionId') connectionId: string,
    @Res() res: Response,
  ) {
    // Fire and forget - don't wait for tracking to complete
    this.followUpService.trackOpen(connectionId).catch(() => {
      // Silently ignore errors
    });

    // Return transparent pixel
    res.setHeader('Content-Type', 'image/gif');
    res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
    res.setHeader('Pragma', 'no-cache');
    return res.status(HttpStatus.OK).send(TRANSPARENT_PIXEL);
  }

  /**
   * Track action click from email.
   * No auth required - called from email link.
   */
  @Get('track/click/:connectionId/:action')
  async trackClick(
    @Param('connectionId') connectionId: string,
    @Param('action') action: string,
    @Query('redirect') redirect: string,
    @Res() res: Response,
  ) {
    // Fire and forget tracking
    this.followUpService.trackAction(connectionId, action).catch(() => {
      // Silently ignore errors
    });

    // Redirect to the target URL
    if (redirect) {
      return res.redirect(redirect);
    }

    // If no redirect, just return success
    return res.status(HttpStatus.OK).json({ tracked: true });
  }

  /**
   * Get follow-up statistics for an event.
   */
  @UseGuards(JwtAuthGuard)
  @Get('stats/:eventId')
  async getFollowUpStats(@Param('eventId') eventId: string) {
    return this.followUpService.getEventFollowUpStats(eventId);
  }

  /**
   * Mark a follow-up as replied (manual trigger).
   */
  @UseGuards(JwtAuthGuard)
  @Post(':connectionId/replied')
  async markReplied(@Param('connectionId') connectionId: string) {
    await this.followUpService.trackAction(connectionId, 'reply');
    return { success: true };
  }
}
