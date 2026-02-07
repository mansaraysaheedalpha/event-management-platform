//src/networking/profile/profile.controller.ts
import {
  Controller,
  Post,
  Get,
  Body,
  UseGuards,
  Req,
  Param,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { ProfileService } from './profile.service';
import { CreateProfileDto, ProfileResponseDto } from './dto';

interface AuthenticatedRequest {
  user: {
    sub: string;
    email: string;
  };
}

/**
 * Profile Controller
 *
 * REST endpoints for managing user networking profiles.
 * Used during event registration to collect data for AI recommendations.
 *
 * Endpoints:
 * - POST /profile - Create or update profile (upsert)
 * - GET /profile - Get current user's profile
 * - GET /profile/completeness - Get profile completeness score
 */
@Controller('profile')
export class ProfileController {
  constructor(private readonly profileService: ProfileService) {}

  /**
   * Create or update the authenticated user's networking profile.
   *
   * Called after event registration with networking preferences.
   * This data is used by the AI recommendation system.
   *
   * @param dto - Profile data including goals, interests, social links
   * @param req - Authenticated request with user info
   * @returns Created/updated profile
   */
  @UseGuards(AuthGuard('jwt'))
  @Post()
  @HttpCode(HttpStatus.OK)
  async upsertProfile(
    @Body() dto: CreateProfileDto,
    @Req() req: AuthenticatedRequest,
  ): Promise<ProfileResponseDto> {
    const userId = req.user.sub;
    return this.profileService.upsertProfile(userId, dto);
  }

  /**
   * Get the authenticated user's profile.
   *
   * Returns 404 if profile doesn't exist.
   */
  @UseGuards(AuthGuard('jwt'))
  @Get()
  async getProfile(
    @Req() req: AuthenticatedRequest,
  ): Promise<ProfileResponseDto> {
    const userId = req.user.sub;
    return this.profileService.getProfile(userId);
  }

  /**
   * Get any user's profile by ID.
   *
   * Allows viewing other attendees' profiles at events.
   */
  @UseGuards(AuthGuard('jwt'))
  @Get('user/:userId')
  async getUserProfile(
    @Param('userId') userId: string,
  ): Promise<ProfileResponseDto> {
    return this.profileService.getProfile(userId);
  }

  /**
   * Get the authenticated user's profile completeness score (0-100).
   *
   * Used to prompt users to complete their profile for better recommendations.
   */
  @UseGuards(AuthGuard('jwt'))
  @Get('completeness')
  async getCompleteness(
    @Req() req: AuthenticatedRequest,
  ): Promise<{ completeness: number; hasProfile: boolean }> {
    const userId = req.user.sub;
    const hasProfile = await this.profileService.hasProfile(userId);
    const completeness = await this.profileService.getProfileCompleteness(
      userId,
    );

    return { completeness, hasProfile };
  }
}
