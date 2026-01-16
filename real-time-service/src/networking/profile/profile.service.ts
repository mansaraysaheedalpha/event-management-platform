//src/networking/profile/profile.service.ts
import { Injectable, Logger, NotFoundException } from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { CreateProfileDto, ProfileResponseDto } from './dto';
import { EventEmitter2 } from '@nestjs/event-emitter';

@Injectable()
export class ProfileService {
  private readonly logger = new Logger(ProfileService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly eventEmitter: EventEmitter2,
  ) {}

  /**
   * Create or update a user's networking profile.
   *
   * Called after event registration with networking preferences.
   * Triggers enrichment if social media URLs are provided.
   */
  async upsertProfile(
    userId: string,
    dto: CreateProfileDto,
  ): Promise<ProfileResponseDto> {
    this.logger.log(`Upserting profile for user ${userId}`);

    // Calculate profile completeness score
    const completeness = this.calculateCompleteness(dto);

    // Prepare data for upsert
    const profileData = {
      goals: dto.goals || [],
      interests: dto.interests || [],
      bio: dto.bio,
      industry: dto.industry,
      skillsToOffer: dto.skillsToOffer || [],
      skillsNeeded: dto.skillsNeeded || [],
      linkedInUrl: dto.linkedInUrl,
      githubUsername: dto.githubUsername,
      twitterHandle: dto.twitterHandle,
      facebookProfileUrl: dto.facebookProfileUrl,
      instagramHandle: dto.instagramHandle,
      youtubeChannelUrl: dto.youtubeChannelUrl,
      personalWebsite: dto.personalWebsite,
    };

    // Upsert the profile
    const profile = await this.prisma.userProfile.upsert({
      where: { userId },
      create: {
        userId,
        ...profileData,
        // Store event expectations in bio if no bio provided
        bio: dto.bio || dto.eventExpectations,
      },
      update: {
        ...profileData,
        // Only update bio if provided, don't overwrite with expectations
        bio: dto.bio || undefined,
        updatedAt: new Date(),
      },
    });

    // Emit event for enrichment if social URLs provided
    if (dto.linkedInUrl || dto.githubUsername || dto.twitterHandle) {
      this.eventEmitter.emit('profile.created', {
        userId,
        linkedInUrl: dto.linkedInUrl,
        githubUsername: dto.githubUsername,
        twitterHandle: dto.twitterHandle,
      });
      this.logger.log(`Emitted profile.created event for enrichment`);
    }

    return this.mapToResponse(profile);
  }

  /**
   * Get a user's profile
   */
  async getProfile(userId: string): Promise<ProfileResponseDto> {
    const profile = await this.prisma.userProfile.findUnique({
      where: { userId },
    });

    if (!profile) {
      throw new NotFoundException('Profile not found');
    }

    return this.mapToResponse(profile);
  }

  /**
   * Check if user has a profile
   */
  async hasProfile(userId: string): Promise<boolean> {
    const count = await this.prisma.userProfile.count({
      where: { userId },
    });
    return count > 0;
  }

  /**
   * Get profile completeness (0-100)
   */
  async getProfileCompleteness(userId: string): Promise<number> {
    const profile = await this.prisma.userProfile.findUnique({
      where: { userId },
      select: {
        goals: true,
        interests: true,
        bio: true,
        industry: true,
        skillsToOffer: true,
        skillsNeeded: true,
        linkedInUrl: true,
        githubUsername: true,
      },
    });

    if (!profile) return 0;

    return this.calculateCompleteness(profile);
  }

  /**
   * Calculate profile completeness percentage
   */
  private calculateCompleteness(data: Partial<CreateProfileDto>): number {
    let score = 0;
    const weights = {
      goals: 20, // Most important for matching
      interests: 20,
      bio: 10,
      industry: 10,
      skillsToOffer: 10,
      skillsNeeded: 10,
      linkedInUrl: 10, // Social links for enrichment
      githubUsername: 5,
      twitterHandle: 5,
    };

    if (data.goals && data.goals.length > 0) score += weights.goals;
    if (data.interests && data.interests.length > 0) score += weights.interests;
    if (data.bio) score += weights.bio;
    if (data.industry) score += weights.industry;
    if (data.skillsToOffer && data.skillsToOffer.length > 0)
      score += weights.skillsToOffer;
    if (data.skillsNeeded && data.skillsNeeded.length > 0)
      score += weights.skillsNeeded;
    if (data.linkedInUrl) score += weights.linkedInUrl;
    if (data.githubUsername) score += weights.githubUsername;
    if (data.twitterHandle) score += weights.twitterHandle;

    return score;
  }

  /**
   * Map database entity to response DTO
   */
  private mapToResponse(profile: any): ProfileResponseDto {
    return {
      id: profile.id,
      userId: profile.userId,
      goals: profile.goals || [],
      interests: profile.interests || [],
      bio: profile.bio,
      industry: profile.industry,
      skillsToOffer: profile.skillsToOffer || [],
      skillsNeeded: profile.skillsNeeded || [],
      linkedInUrl: profile.linkedInUrl,
      githubUsername: profile.githubUsername,
      twitterHandle: profile.twitterHandle,
      profileCompleteness: this.calculateCompleteness(profile),
      createdAt: profile.createdAt,
      updatedAt: profile.updatedAt,
    };
  }
}
