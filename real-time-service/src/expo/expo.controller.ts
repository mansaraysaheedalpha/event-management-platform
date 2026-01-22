// src/expo/expo.controller.ts
import {
  Controller,
  Get,
  Post,
  Patch,
  Body,
  Param,
  Query,
  UseGuards,
  Logger,
  HttpCode,
  HttpStatus,
  NotFoundException,
  ForbiddenException,
} from '@nestjs/common';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { ExpoService } from './expo.service';
import { ExpoAnalyticsService } from './expo-analytics.service';

interface JwtUser {
  sub: string;
  email: string;
  orgId: string;
  permissions?: string[];
}

interface CreateHallDto {
  eventId: string;
  name: string;
  description?: string;
  categories?: string[];
}

interface UpdateHallDto {
  name?: string;
  description?: string;
  categories?: string[];
  isActive?: boolean;
}

interface CreateBoothDto {
  hallId: string;
  name: string;
  tagline?: string;
  description?: string;
  tier?: 'PLATINUM' | 'GOLD' | 'SILVER' | 'BRONZE' | 'STARTUP';
  logoUrl?: string;
  bannerUrl?: string;
  videoUrl?: string;
  category?: string;
  sponsorId?: string;
}

interface UpdateBoothDto {
  name?: string;
  tagline?: string;
  description?: string;
  tier?: 'PLATINUM' | 'GOLD' | 'SILVER' | 'BRONZE' | 'STARTUP';
  logoUrl?: string;
  bannerUrl?: string;
  videoUrl?: string;
  category?: string;
  chatEnabled?: boolean;
  videoEnabled?: boolean;
  displayOrder?: number;
}

/**
 * REST API controller for expo hall and booth management.
 *
 * These endpoints provide an alternative to WebSocket-based management,
 * useful for:
 * - Bulk operations
 * - Third-party integrations
 * - Admin tools that don't need real-time updates
 */
@Controller('api/expo')
@UseGuards(JwtAuthGuard)
export class ExpoController {
  private readonly logger = new Logger(ExpoController.name);

  constructor(
    private readonly expoService: ExpoService,
    private readonly analyticsService: ExpoAnalyticsService,
  ) {}

  /**
   * Check if user has expo management permission
   */
  private hasManagePermission(user: JwtUser): boolean {
    return (
      user.permissions?.includes('expo:manage') ||
      user.permissions?.includes('event:manage') ||
      false
    );
  }

  // ==========================================
  // EXPO HALL ENDPOINTS
  // ==========================================

  /**
   * Get expo hall for an event
   */
  @Get('halls/:eventId')
  async getHall(
    @Param('eventId') eventId: string,
    @CurrentUser() _user: JwtUser,
  ) {
    const hall = await this.expoService.getExpoHallSafe(eventId);

    if (!hall) {
      throw new NotFoundException('No expo hall found for this event');
    }

    return {
      success: true,
      hall,
    };
  }

  /**
   * Create an expo hall for an event
   */
  @Post('halls')
  @HttpCode(HttpStatus.CREATED)
  async createHall(@Body() dto: CreateHallDto, @CurrentUser() user: JwtUser) {
    if (!this.hasManagePermission(user)) {
      throw new ForbiddenException(
        'You do not have permission to create expo halls',
      );
    }

    const hall = await this.expoService.createExpoHall(
      dto.eventId,
      user.orgId,
      {
        name: dto.name,
        description: dto.description,
        categories: dto.categories,
      },
    );

    this.logger.log(`Created expo hall ${hall.id} for event ${dto.eventId}`);

    return {
      success: true,
      hall,
    };
  }

  /**
   * Update an expo hall
   */
  @Patch('halls/:hallId')
  async updateHall(
    @Param('hallId') hallId: string,
    @Body() dto: UpdateHallDto,
    @CurrentUser() user: JwtUser,
  ) {
    if (!this.hasManagePermission(user)) {
      throw new ForbiddenException(
        'You do not have permission to update expo halls',
      );
    }

    const hall = await this.expoService.updateExpoHall(hallId, dto);

    this.logger.log(`Updated expo hall ${hallId}`);

    return {
      success: true,
      hall,
    };
  }

  // ==========================================
  // BOOTH ENDPOINTS
  // ==========================================

  /**
   * List booths in an expo hall
   */
  @Get('halls/:hallId/booths')
  async listBooths(
    @Param('hallId') hallId: string,
    @Query('tier') tier?: string,
    @Query('category') category?: string,
  ) {
    // Get hall with booths
    const hall = await this.expoService.getExpoHallById(hallId);

    if (!hall) {
      throw new NotFoundException('Expo hall not found');
    }

    let booths = hall.booths || [];

    // Apply filters
    if (tier) {
      booths = booths.filter((b) => b.tier === tier.toUpperCase());
    }
    if (category) {
      booths = booths.filter((b) => b.category === category);
    }

    return {
      success: true,
      booths,
      total: booths.length,
    };
  }

  /**
   * Get a single booth
   */
  @Get('booths/:boothId')
  async getBooth(@Param('boothId') boothId: string) {
    const booth = await this.expoService.getBooth(boothId);

    return {
      success: true,
      booth,
    };
  }

  /**
   * Create a booth
   */
  @Post('booths')
  @HttpCode(HttpStatus.CREATED)
  async createBooth(@Body() dto: CreateBoothDto, @CurrentUser() user: JwtUser) {
    if (!this.hasManagePermission(user)) {
      throw new ForbiddenException(
        'You do not have permission to create booths',
      );
    }

    const booth = await this.expoService.createBooth(dto.hallId, user.orgId, {
      name: dto.name,
      tagline: dto.tagline,
      description: dto.description,
      tier: dto.tier,
      logoUrl: dto.logoUrl,
      bannerUrl: dto.bannerUrl,
      videoUrl: dto.videoUrl,
      category: dto.category,
      sponsorId: dto.sponsorId,
    });

    this.logger.log(`Created booth ${booth.id} in hall ${dto.hallId}`);

    return {
      success: true,
      booth,
    };
  }

  /**
   * Update a booth
   */
  @Patch('booths/:boothId')
  async updateBooth(
    @Param('boothId') boothId: string,
    @Body() dto: UpdateBoothDto,
    @CurrentUser() user: JwtUser,
  ) {
    if (!this.hasManagePermission(user)) {
      throw new ForbiddenException(
        'You do not have permission to update booths',
      );
    }

    const booth = await this.expoService.updateBooth(boothId, dto);

    this.logger.log(`Updated booth ${boothId}`);

    return {
      success: true,
      booth,
    };
  }

  // ==========================================
  // ANALYTICS ENDPOINTS
  // ==========================================

  /**
   * Get booth analytics
   */
  @Get('booths/:boothId/analytics')
  async getBoothAnalytics(
    @Param('boothId') boothId: string,
    @CurrentUser() user: JwtUser,
  ) {
    // Check if user is staff or has manage permission
    const isStaff = await this.expoService.isBoothStaff(user.sub, boothId);
    if (!isStaff && !this.hasManagePermission(user)) {
      throw new ForbiddenException(
        'You do not have permission to view booth analytics',
      );
    }

    const stats = await this.analyticsService.getRealtimeStats(boothId);

    return {
      success: true,
      stats,
    };
  }

  /**
   * Get expo hall analytics (aggregate across all booths)
   */
  @Get('halls/:hallId/analytics')
  async getHallAnalytics(
    @Param('hallId') hallId: string,
    @CurrentUser() user: JwtUser,
  ) {
    if (!this.hasManagePermission(user)) {
      throw new ForbiddenException(
        'You do not have permission to view hall analytics',
      );
    }

    const hall = await this.expoService.getExpoHallById(hallId);
    if (!hall) {
      throw new NotFoundException('Expo hall not found');
    }

    // Aggregate analytics across all booths
    const boothStats = await Promise.all(
      (hall.booths || []).map(async (booth) => {
        const stats = await this.analyticsService.getRealtimeStats(booth.id);
        return {
          boothId: booth.id,
          boothName: booth.name,
          tier: booth.tier,
          ...stats,
        };
      }),
    );

    // Calculate totals
    const totals = boothStats.reduce(
      (acc, stats) => ({
        totalVisitors: acc.totalVisitors + (stats.totalVisitors || 0),
        currentVisitors: acc.currentVisitors + (stats.currentVisitors || 0),
        uniqueVisitors: acc.uniqueVisitors + (stats.uniqueVisitors || 0),
        totalLeads: acc.totalLeads + (stats.totalLeads || 0),
        totalDownloads: acc.totalDownloads + (stats.totalDownloads || 0),
        totalCtaClicks: acc.totalCtaClicks + (stats.totalCtaClicks || 0),
      }),
      {
        totalVisitors: 0,
        currentVisitors: 0,
        uniqueVisitors: 0,
        totalLeads: 0,
        totalDownloads: 0,
        totalCtaClicks: 0,
      },
    );

    return {
      success: true,
      totals,
      booths: boothStats,
    };
  }
}
