// src/expo/expo.controller.ts
import {
  Controller,
  Get,
  Post,
  Patch,
  Delete,
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

interface AddResourceDto {
  name: string;
  description?: string;
  type: 'PDF' | 'VIDEO' | 'IMAGE' | 'DOCUMENT' | 'LINK';
  url: string;
  thumbnailUrl?: string;
  fileSize?: number;
}

interface UpdateResourceDto {
  name?: string;
  description?: string;
  url?: string;
  thumbnailUrl?: string;
}

interface AddCtaDto {
  label: string;
  url: string;
  style?: 'primary' | 'secondary' | 'outline';
  icon?: string;
}

interface UpdateCtaDto {
  label?: string;
  url?: string;
  style?: 'primary' | 'secondary' | 'outline';
  icon?: string;
}

interface AddStaffDto {
  staffId: string;
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

  // ==========================================
  // SPONSOR BOOTH MANAGEMENT ENDPOINTS
  // ==========================================

  /**
   * Get sponsor's own booth by sponsorId
   * Sponsors can use this to find and manage their booth
   */
  @Get('sponsor/:sponsorId/booth')
  async getSponsorBooth(
    @Param('sponsorId') sponsorId: string,
    @CurrentUser() user: JwtUser,
  ) {
    const booth = await this.expoService.getBoothForSponsor(sponsorId);

    if (!booth) {
      throw new NotFoundException('No booth found for this sponsor');
    }

    // Check authorization: user must be booth staff or have manage permission
    const isStaff = await this.expoService.isBoothStaff(user.sub, booth.id);
    if (!isStaff && !this.hasManagePermission(user)) {
      throw new ForbiddenException(
        'You do not have permission to view this booth',
      );
    }

    return {
      success: true,
      booth,
    };
  }

  /**
   * Check if user can manage booth (staff or has manage permission)
   */
  private async canManageBooth(
    userId: string,
    boothId: string,
    user: JwtUser,
  ): Promise<boolean> {
    const isStaff = await this.expoService.isBoothStaff(userId, boothId);
    return isStaff || this.hasManagePermission(user);
  }

  // ==========================================
  // BOOTH RESOURCE MANAGEMENT
  // ==========================================

  /**
   * Add a resource to a booth
   */
  @Post('booths/:boothId/resources')
  @HttpCode(HttpStatus.CREATED)
  async addResource(
    @Param('boothId') boothId: string,
    @Body() dto: AddResourceDto,
    @CurrentUser() user: JwtUser,
  ) {
    if (!(await this.canManageBooth(user.sub, boothId, user))) {
      throw new ForbiddenException(
        'You do not have permission to manage this booth',
      );
    }

    const result = await this.expoService.addBoothResource(boothId, dto);

    this.logger.log(`Added resource to booth ${boothId}`);

    return {
      success: true,
      resource: result.resource,
    };
  }

  /**
   * Update a resource in a booth
   */
  @Patch('booths/:boothId/resources/:resourceId')
  async updateResource(
    @Param('boothId') boothId: string,
    @Param('resourceId') resourceId: string,
    @Body() dto: UpdateResourceDto,
    @CurrentUser() user: JwtUser,
  ) {
    if (!(await this.canManageBooth(user.sub, boothId, user))) {
      throw new ForbiddenException(
        'You do not have permission to manage this booth',
      );
    }

    const result = await this.expoService.updateBoothResource(
      boothId,
      resourceId,
      dto,
    );

    this.logger.log(`Updated resource ${resourceId} in booth ${boothId}`);

    return {
      success: true,
      resource: result.resource,
    };
  }

  /**
   * Remove a resource from a booth
   */
  @Delete('booths/:boothId/resources/:resourceId')
  async removeResource(
    @Param('boothId') boothId: string,
    @Param('resourceId') resourceId: string,
    @CurrentUser() user: JwtUser,
  ) {
    if (!(await this.canManageBooth(user.sub, boothId, user))) {
      throw new ForbiddenException(
        'You do not have permission to manage this booth',
      );
    }

    await this.expoService.removeBoothResource(boothId, resourceId);

    this.logger.log(`Removed resource ${resourceId} from booth ${boothId}`);

    return {
      success: true,
      message: 'Resource removed successfully',
    };
  }

  // ==========================================
  // BOOTH CTA MANAGEMENT
  // ==========================================

  /**
   * Add a CTA button to a booth
   */
  @Post('booths/:boothId/ctas')
  @HttpCode(HttpStatus.CREATED)
  async addCta(
    @Param('boothId') boothId: string,
    @Body() dto: AddCtaDto,
    @CurrentUser() user: JwtUser,
  ) {
    if (!(await this.canManageBooth(user.sub, boothId, user))) {
      throw new ForbiddenException(
        'You do not have permission to manage this booth',
      );
    }

    const result = await this.expoService.addBoothCta(boothId, dto);

    this.logger.log(`Added CTA to booth ${boothId}`);

    return {
      success: true,
      cta: result.cta,
    };
  }

  /**
   * Update a CTA button in a booth
   */
  @Patch('booths/:boothId/ctas/:ctaId')
  async updateCta(
    @Param('boothId') boothId: string,
    @Param('ctaId') ctaId: string,
    @Body() dto: UpdateCtaDto,
    @CurrentUser() user: JwtUser,
  ) {
    if (!(await this.canManageBooth(user.sub, boothId, user))) {
      throw new ForbiddenException(
        'You do not have permission to manage this booth',
      );
    }

    const result = await this.expoService.updateBoothCta(boothId, ctaId, dto);

    this.logger.log(`Updated CTA ${ctaId} in booth ${boothId}`);

    return {
      success: true,
      cta: result.cta,
    };
  }

  /**
   * Remove a CTA button from a booth
   */
  @Delete('booths/:boothId/ctas/:ctaId')
  async removeCta(
    @Param('boothId') boothId: string,
    @Param('ctaId') ctaId: string,
    @CurrentUser() user: JwtUser,
  ) {
    if (!(await this.canManageBooth(user.sub, boothId, user))) {
      throw new ForbiddenException(
        'You do not have permission to manage this booth',
      );
    }

    await this.expoService.removeBoothCta(boothId, ctaId);

    this.logger.log(`Removed CTA ${ctaId} from booth ${boothId}`);

    return {
      success: true,
      message: 'CTA removed successfully',
    };
  }

  // ==========================================
  // BOOTH STAFF MANAGEMENT
  // ==========================================

  /**
   * Add a staff member to a booth
   */
  @Post('booths/:boothId/staff')
  @HttpCode(HttpStatus.CREATED)
  async addStaff(
    @Param('boothId') boothId: string,
    @Body() dto: AddStaffDto,
    @CurrentUser() user: JwtUser,
  ) {
    if (!(await this.canManageBooth(user.sub, boothId, user))) {
      throw new ForbiddenException(
        'You do not have permission to manage this booth',
      );
    }

    const booth = await this.expoService.addBoothStaff(boothId, dto.staffId);

    this.logger.log(`Added staff ${dto.staffId} to booth ${boothId}`);

    return {
      success: true,
      booth,
    };
  }

  /**
   * Remove a staff member from a booth
   */
  @Delete('booths/:boothId/staff/:staffId')
  async removeStaff(
    @Param('boothId') boothId: string,
    @Param('staffId') staffId: string,
    @CurrentUser() user: JwtUser,
  ) {
    if (!(await this.canManageBooth(user.sub, boothId, user))) {
      throw new ForbiddenException(
        'You do not have permission to manage this booth',
      );
    }

    const booth = await this.expoService.removeBoothStaff(boothId, staffId);

    this.logger.log(`Removed staff ${staffId} from booth ${boothId}`);

    return {
      success: true,
      booth,
    };
  }

  /**
   * Sponsor updates their own booth details
   */
  @Patch('sponsor/:sponsorId/booth')
  async updateSponsorBooth(
    @Param('sponsorId') sponsorId: string,
    @Body() dto: UpdateBoothDto,
    @CurrentUser() user: JwtUser,
  ) {
    const booth = await this.expoService.getBoothForSponsor(sponsorId);

    if (!booth) {
      throw new NotFoundException('No booth found for this sponsor');
    }

    // Check authorization
    if (!(await this.canManageBooth(user.sub, booth.id, user))) {
      throw new ForbiddenException(
        'You do not have permission to update this booth',
      );
    }

    const updatedBooth = await this.expoService.updateBooth(booth.id, dto);

    this.logger.log(`Sponsor ${sponsorId} updated their booth ${booth.id}`);

    return {
      success: true,
      booth: updatedBooth,
    };
  }

  // ==========================================
  // SPONSOR LEAD MANAGEMENT
  // ==========================================

  /**
   * Calculate intent score based on engagement actions.
   * Returns { score: 0-100, level: 'hot' | 'warm' | 'cold' }
   */
  private calculateIntentScore(lead: any): { score: number; level: 'hot' | 'warm' | 'cold' } {
    let score = 0;
    const actions = (lead.actions || []) as Array<{ action: string }>;
    const duration = lead.durationSeconds || 0;

    // Action scoring (max 70 points)
    const videoActions = actions.filter(a => a.action === 'video_watch' || a.action === 'video_call');
    const chatActions = actions.filter(a => a.action === 'chat_message');
    const downloadActions = actions.filter(a => a.action === 'resource_download');
    const ctaActions = actions.filter(a => a.action === 'cta_click');

    // Video call/watch: 25 points (highest intent signal)
    if (videoActions.length > 0) {
      score += 25;
    }

    // Multiple chats: 15 points
    if (chatActions.length >= 3) {
      score += 15;
    } else if (chatActions.length > 0) {
      score += 10;
    }

    // Resource downloads: 15 points
    if (downloadActions.length >= 2) {
      score += 15;
    } else if (downloadActions.length > 0) {
      score += 10;
    }

    // CTA clicks: 10 points
    if (ctaActions.length > 0) {
      score += 10;
    }

    // Time spent (max 30 points)
    if (duration >= 300) { // 5+ minutes
      score += 30;
    } else if (duration >= 120) { // 2+ minutes
      score += 20;
    } else if (duration >= 60) { // 1+ minute
      score += 10;
    }

    // Categorize
    let level: 'hot' | 'warm' | 'cold';
    if (score >= 60) {
      level = 'hot';
    } else if (score >= 30) {
      level = 'warm';
    } else {
      level = 'cold';
    }

    return { score, level };
  }

  /**
   * Get lead statistics for a sponsor's booth from MongoDB.
   * This is the same data source as the Booth Dashboard.
   */
  @Get('sponsor/:sponsorId/leads/stats')
  async getSponsorLeadStats(
    @Param('sponsorId') sponsorId: string,
    @CurrentUser() user: JwtUser,
  ) {
    const booth = await this.expoService.getBoothForSponsor(sponsorId);

    if (!booth) {
      throw new NotFoundException('No booth found for this sponsor');
    }

    // Check authorization
    if (!(await this.canManageBooth(user.sub, booth.id, user))) {
      throw new ForbiddenException(
        'You do not have permission to view booth leads',
      );
    }

    // Get all leads for this booth
    const allLeads = await this.analyticsService.getRecentLeads(booth.id, 1000);

    // Calculate intent scores for each lead
    let hot_leads = 0;
    let warm_leads = 0;
    let cold_leads = 0;
    let total_score = 0;

    allLeads.forEach(lead => {
      const { score, level } = this.calculateIntentScore(lead);
      total_score += score;

      if (level === 'hot') {
        hot_leads++;
      } else if (level === 'warm') {
        warm_leads++;
      } else {
        cold_leads++;
      }
    });

    const total_leads = allLeads.length;
    const avg_intent_score = total_leads > 0 ? total_score / total_leads : 0;

    return {
      total_leads,
      hot_leads,
      warm_leads,
      cold_leads,
      leads_contacted: 0, // TODO: Track contacted status
      leads_converted: 0, // TODO: Track conversion status
      conversion_rate: 0,
      avg_intent_score: Math.round(avg_intent_score),
    };
  }

  /**
   * Get recent leads for a sponsor's booth from MongoDB.
   * This is the same data source as the Booth Dashboard.
   */
  @Get('sponsor/:sponsorId/leads')
  async getSponsorLeads(
    @Param('sponsorId') sponsorId: string,
    @Query('limit') limitStr?: string,
    @CurrentUser() user?: JwtUser,
  ) {
    const booth = await this.expoService.getBoothForSponsor(sponsorId);

    if (!booth) {
      throw new NotFoundException('No booth found for this sponsor');
    }

    // Check authorization
    if (user && !(await this.canManageBooth(user.sub, booth.id, user))) {
      throw new ForbiddenException(
        'You do not have permission to view booth leads',
      );
    }

    const limit = limitStr ? parseInt(limitStr, 10) : 50;
    const leads = await this.analyticsService.getRecentLeads(booth.id, limit);

    // Transform to match expected format with intent scoring
    return leads.map((lead) => {
      const { score, level } = this.calculateIntentScore(lead);

      return {
        id: lead.visitorId,
        user_id: lead.visitorId,
        user_name: lead.visitorName,
        user_email: (lead.formData as any)?.email,
        user_company: (lead.formData as any)?.company,
        intent_level: level,
        intent_score: score,
        created_at: lead.capturedAt,
        is_starred: false,
      };
    });
  }
}
