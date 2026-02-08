//src/networking/linkedin/linkedin.controller.ts
import {
  Controller,
  Get,
  Post,
  Delete,
  Query,
  Param,
  Res,
  UseGuards,
  Req,
  HttpStatus,
  Inject,
} from '@nestjs/common';
import { Response } from 'express';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { JwtAuthGuard } from 'src/common/guards/jwt-auth.guard';
import { LinkedInService } from './linkedin.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { Redis } from 'ioredis';
import { randomBytes } from 'crypto';

interface AuthenticatedRequest extends Request {
  user: { sub: string; email: string };
}

// Redis key prefix for OAuth state
const OAUTH_STATE_PREFIX = 'linkedin:oauth:state:';
const OAUTH_STATE_TTL_SECONDS = 600; // 10 minutes

@ApiTags('LinkedIn')
@Controller('linkedin')
export class LinkedInController {
  constructor(
    private readonly linkedInService: LinkedInService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
  ) {}

  /**
   * Initiate LinkedIn OAuth flow.
   * Returns the authorization URL to redirect the user to.
   */
  @UseGuards(JwtAuthGuard)
  @Get('auth/init')
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Initiate LinkedIn OAuth flow' })
  async initiateAuth(@Req() req: AuthenticatedRequest) {
    // Generate a random state for CSRF protection
    const state = randomBytes(32).toString('hex');

    // Store state with user ID in Redis (expires in 10 minutes)
    await this.redis.setex(
      `${OAUTH_STATE_PREFIX}${state}`,
      OAUTH_STATE_TTL_SECONDS,
      JSON.stringify({ userId: req.user.sub }),
    );

    const authUrl = this.linkedInService.getAuthorizationUrl(state);

    return { authUrl, state };
  }

  /**
   * Handle LinkedIn OAuth callback.
   * This endpoint is called by LinkedIn after user authorization.
   */
  @Get('auth/callback')
  @ApiOperation({ summary: 'Handle LinkedIn OAuth callback' })
  async handleCallback(
    @Query('code') code: string,
    @Query('state') state: string,
    @Query('error') error: string,
    @Query('error_description') errorDescription: string,
    @Res() res: Response,
  ) {
    const frontendUrl = (process.env.FRONTEND_URL || 'http://localhost:3000').split(',')[0].trim();

    // Handle error from LinkedIn
    if (error) {
      return res.redirect(
        `${frontendUrl}/settings/linkedin?error=${encodeURIComponent(errorDescription || error)}`,
      );
    }

    // Validate state from Redis
    const stateKey = `${OAUTH_STATE_PREFIX}${state}`;
    const storedStateJson = await this.redis.get(stateKey);

    if (!storedStateJson) {
      return res.redirect(
        `${frontendUrl}/settings/linkedin?error=${encodeURIComponent('Invalid or expired state parameter')}`,
      );
    }

    // Parse and clean up state atomically
    const storedState = JSON.parse(storedStateJson) as { userId: string };
    await this.redis.del(stateKey);

    try {
      // Connect LinkedIn account
      await this.linkedInService.connectLinkedIn(storedState.userId, code);

      return res.redirect(`${frontendUrl}/settings/linkedin?success=true`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to connect LinkedIn';
      return res.redirect(
        `${frontendUrl}/settings/linkedin?error=${encodeURIComponent(message)}`,
      );
    }
  }

  /**
   * Disconnect LinkedIn from the user's account.
   */
  @UseGuards(JwtAuthGuard)
  @Delete('disconnect')
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Disconnect LinkedIn account' })
  async disconnect(@Req() req: AuthenticatedRequest) {
    await this.linkedInService.disconnectLinkedIn(req.user.sub);
    return { success: true };
  }

  /**
   * Check if the user has LinkedIn connected.
   */
  @UseGuards(JwtAuthGuard)
  @Get('status')
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Check LinkedIn connection status' })
  async getStatus(@Req() req: AuthenticatedRequest) {
    const isConnected = await this.linkedInService.isLinkedInConnected(req.user.sub);
    return { isConnected };
  }

  /**
   * Get LinkedIn connection suggestions for event connections.
   */
  @UseGuards(JwtAuthGuard)
  @Get('suggestions/:eventId')
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Get LinkedIn connection suggestions' })
  async getSuggestions(
    @Req() req: AuthenticatedRequest,
    @Param('eventId') eventId: string,
  ) {
    return this.linkedInService.getLinkedInSuggestions(req.user.sub, eventId);
  }

  /**
   * Get LinkedIn profile URL for a user.
   */
  @UseGuards(JwtAuthGuard)
  @Get('profile/:userId')
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Get LinkedIn profile URL for a user' })
  async getProfileUrl(@Param('userId') userId: string) {
    const linkedInUrl = await this.linkedInService.getLinkedInUrl(userId);
    return { linkedInUrl };
  }

  /**
   * Generate a suggested LinkedIn connection message.
   */
  @UseGuards(JwtAuthGuard)
  @Get('message/suggest')
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Generate suggested LinkedIn connection message' })
  async getSuggestedMessage(
    @Query('userName') userName: string,
    @Query('eventName') eventName: string,
    @Query('context') context?: string,
  ) {
    const message = this.linkedInService.generateConnectionMessage(
      userName,
      eventName,
      context,
    );
    return { message };
  }
}
