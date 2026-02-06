//src/networking/recommendations/recommendations.service.ts
import {
  Injectable,
  Logger,
  NotFoundException,
  BadRequestException,
  Inject,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { HttpService } from '@nestjs/axios';
import { PrismaService } from 'src/prisma.service';
import { firstValueFrom } from 'rxjs';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { getOracleAIBreaker, CircuitBreakerOpenError } from 'src/common/utils/circuit-breaker';
import {
  RecommendationDto,
  RecommendationsResponseDto,
  RecommendedUserInfo,
  ConnectionDto,
  ConnectionsResponseDto,
  ConnectedUserInfo,
} from './dto';
import { Recommendation } from '@prisma/client';
import { KafkaService } from 'src/shared/kafka/kafka.service';

/**
 * Interface for oracle-ai-service recommendation request
 */
interface OracleRecommendationRequest {
  userId: string;
  eventId: string;
  userProfile: UserProfileData;
  candidates: CandidateData[];
  limit?: number;
}

/**
 * Interface for oracle-ai-service recommendation response
 */
interface OracleRecommendationResponse {
  recommendations: Array<{
    userId: string;
    matchScore: number;
    reasons: string[];
    conversationStarters: string[];
    potentialValue?: string;
  }>;
}

interface UserProfileData {
  id: string;
  name: string;
  role?: string;
  company?: string;
  industry?: string;
  goals: string[];
  interests: string[];
  skillsToOffer: string[];
  skillsNeeded: string[];
  bio?: string;
  linkedInHeadline?: string;
  githubTopLanguages: string[];
  githubRepoCount?: number;
  extractedSkills: string[];
}

interface CandidateData extends UserProfileData {
  avatarUrl?: string;
  linkedInUrl?: string;
  githubUsername?: string;
  twitterHandle?: string;
}

@Injectable()
export class RecommendationsService {
  private readonly logger = new Logger(RecommendationsService.name);
  private readonly CACHE_TTL_SECONDS = 300; // 5 minutes cache for fast lookups
  private readonly RECOMMENDATION_TTL_HOURS = 24; // Recommendations expire after 24h

  constructor(
    private readonly prisma: PrismaService,
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
    private readonly kafkaService: KafkaService,
  ) {}

  /**
   * Get recommendations for a user at an event.
   * Uses caching strategy: Redis -> DB -> Generate new
   */
  async getRecommendations(
    userId: string,
    eventId: string,
    options: { limit?: number; refresh?: boolean } = {},
  ): Promise<RecommendationsResponseDto> {
    const { limit = 10, refresh = false } = options;

    // If refresh requested, generate new recommendations
    if (refresh) {
      this.logger.log(`Force refresh requested for user ${userId}`);
      return this.generateAndStoreRecommendations(userId, eventId, limit);
    }

    // Try Redis cache first
    const cacheKey = this.getCacheKey(userId, eventId);
    const cached = await this.redis.get(cacheKey);
    if (cached) {
      this.logger.debug(`Cache hit for ${cacheKey}`);
      return JSON.parse(cached);
    }

    // Try DB for valid (non-expired) recommendations
    const dbRecommendations = await this.getValidDbRecommendations(
      userId,
      eventId,
    );
    if (dbRecommendations.length > 0) {
      this.logger.debug(`DB hit for user ${userId} at event ${eventId}`);
      const response = await this.buildResponse(dbRecommendations, limit);
      // Cache for fast subsequent access
      await this.redis.setex(cacheKey, this.CACHE_TTL_SECONDS, JSON.stringify(response));
      return response;
    }

    // Generate new recommendations
    this.logger.log(`Generating new recommendations for user ${userId}`);
    return this.generateAndStoreRecommendations(userId, eventId, limit);
  }

  /**
   * Generate new recommendations using oracle-ai-service
   */
  private async generateAndStoreRecommendations(
    userId: string,
    eventId: string,
    limit: number,
  ): Promise<RecommendationsResponseDto> {
    try {
      // Get user profile
      const userProfile = await this.getUserProfileData(userId);
      if (!userProfile) {
        throw new NotFoundException('User profile not found');
      }

      // Get candidate attendees at the event
      const candidates = await this.getEventCandidates(eventId, userId);
      if (candidates.length === 0) {
        return {
          recommendations: [],
          total: 0,
          hasMore: false,
        };
      }

      // Call oracle-ai-service
      const oracleResponse = await this.callOracleService({
        userId,
        eventId,
        userProfile,
        candidates,
        limit: Math.min(limit, 10), // Oracle returns max 10
      });

      // Store recommendations in DB
      const storedRecs = await this.storeRecommendations(
        userId,
        eventId,
        oracleResponse.recommendations,
      );

      // Build response with user info
      const response = await this.buildResponse(storedRecs, limit);

      // Cache the response
      const cacheKey = this.getCacheKey(userId, eventId);
      await this.redis.setex(cacheKey, this.CACHE_TTL_SECONDS, JSON.stringify(response));

      return response;
    } catch (error) {
      this.logger.error(`Failed to generate recommendations: ${error}`);
      throw new BadRequestException('Unable to generate recommendations');
    }
  }

  /**
   * Call oracle-ai-service for LLM-based recommendations.
   * Protected by circuit breaker to prevent cascade failures.
   *
   * Calls two oracle endpoints:
   * 1. /oracle/networking/matchmaking - for match scores and reasons
   * 2. /oracle/networking/conversation-starters - for ice-breakers
   */
  private async callOracleService(
    request: OracleRecommendationRequest,
  ): Promise<OracleRecommendationResponse> {
    const oracleUrl = this.configService.get<string>(
      'ORACLE_AI_SERVICE_URL',
      'http://localhost:8000',
    );

    const breaker = getOracleAIBreaker();

    // Check if circuit is open - use fallback immediately
    if (breaker.isOpen()) {
      this.logger.warn('Oracle AI circuit breaker is open, using fallback recommendations');
      return this.generateFallbackRecommendations(request);
    }

    try {
      return await breaker.execute(async () => {
        // Transform request to oracle's expected format (rich profile for LLM matching)
        const oracleRequest = {
          primary_user: {
            user_id: request.userProfile.id,
            interests: request.userProfile.interests,
            name: request.userProfile.name,
            role: request.userProfile.role,
            company: request.userProfile.company,
            industry: request.userProfile.industry,
            goals: request.userProfile.goals,
            skills_to_offer: request.userProfile.skillsToOffer,
            skills_needed: request.userProfile.skillsNeeded,
            bio: request.userProfile.bio,
            headline: request.userProfile.linkedInHeadline,
          },
          other_users: request.candidates.map((c) => ({
            user_id: c.id,
            interests: c.interests,
            name: c.name,
            role: c.role,
            company: c.company,
            industry: c.industry,
            goals: c.goals,
            skills_to_offer: c.skillsToOffer,
            skills_needed: c.skillsNeeded,
            bio: c.bio,
            headline: c.linkedInHeadline,
          })),
          max_matches: request.limit || 10,
        };

        // Call matchmaking endpoint
        const matchResponse = await firstValueFrom(
          this.httpService.post<{
            matches: Array<{
              user_id: string;
              match_score: number;
              common_interests: string[];
              match_reasons: string[];
            }>;
          }>(
            `${oracleUrl}/oracle/networking/matchmaking`,
            oracleRequest,
            {
              headers: { 'Content-Type': 'application/json' },
              timeout: 30000,
            },
          ),
        );

        // Get conversation starters for top matches
        const recommendations = await Promise.all(
          matchResponse.data.matches.map(async (match) => {
            let conversationStarters: string[] = [];
            try {
              // Find candidate profile for richer starter context
              const candidateProfile = request.candidates.find(
                (c) => c.id === match.user_id,
              );
              const starterResponse = await firstValueFrom(
                this.httpService.post<{ conversation_starters: string[] }>(
                  `${oracleUrl}/oracle/networking/conversation-starters`,
                  {
                    user1_id: request.userProfile.id,
                    user2_id: match.user_id,
                    common_interests: match.common_interests,
                    user1_name: request.userProfile.name,
                    user1_role: request.userProfile.role,
                    user1_company: request.userProfile.company,
                    user1_bio: request.userProfile.bio,
                    user2_name: candidateProfile?.name,
                    user2_role: candidateProfile?.role,
                    user2_company: candidateProfile?.company,
                    user2_bio: candidateProfile?.bio,
                    match_reasons: match.match_reasons,
                  },
                  {
                    headers: { 'Content-Type': 'application/json' },
                    timeout: 15000,
                  },
                ),
              );
              conversationStarters = starterResponse.data.conversation_starters;
            } catch {
              // Use fallback starters if conversation starter call fails
              conversationStarters = this.generateFallbackStarters(match.common_interests);
            }

            return {
              userId: match.user_id,
              matchScore: Math.round(match.match_score * 100), // Convert 0-1 to 0-100
              reasons: match.match_reasons,
              conversationStarters,
            };
          }),
        );

        return { recommendations };
      });
    } catch (error) {
      if (error instanceof CircuitBreakerOpenError) {
        this.logger.warn('Oracle AI circuit breaker opened, using fallback recommendations');
      } else {
        this.logger.error(`Oracle service call failed: ${error}`);
      }
      // Fallback to basic recommendations if oracle fails
      return this.generateFallbackRecommendations(request);
    }
  }

  /**
   * Generate fallback conversation starters based on common interests.
   */
  private generateFallbackStarters(commonInterests: string[]): string[] {
    if (commonInterests.length === 0) {
      return [
        "What brings you to this event?",
        "What's been the highlight of the event for you so far?",
      ];
    }
    const interest = commonInterests[0];
    return [
      `I noticed we both share an interest in ${interest}. What got you started in that area?`,
      `How are you applying ${interest} in your current work?`,
    ];
  }

  /**
   * Fallback recommendation logic when oracle service is unavailable.
   * Uses simple heuristics based on goals and interests overlap.
   */
  private generateFallbackRecommendations(
    request: OracleRecommendationRequest,
  ): OracleRecommendationResponse {
    this.logger.warn('Using fallback recommendation logic');

    const userGoals = new Set(request.userProfile.goals);
    const userInterests = new Set(request.userProfile.interests);

    const scored = request.candidates.map((candidate) => {
      let score = 0;
      const reasons: string[] = [];

      // Goal compatibility
      const candidateGoals = new Set(candidate.goals);
      const goalMatches = this.getGoalCompatibility(userGoals, candidateGoals);
      score += goalMatches * 20;
      if (goalMatches > 0) {
        reasons.push(`Complementary networking goals`);
      }

      // Interest overlap
      const candidateInterests = new Set(candidate.interests);
      const interestOverlap = [...userInterests].filter((i) =>
        candidateInterests.has(i),
      ).length;
      score += interestOverlap * 15;
      if (interestOverlap > 0) {
        reasons.push(`Shared interests in ${[...userInterests].filter((i) => candidateInterests.has(i)).slice(0, 2).join(', ')}`);
      }

      // Skills exchange potential
      const skillsToOfferMatch = candidate.skillsToOffer.some((s) =>
        request.userProfile.skillsNeeded.includes(s),
      );
      const skillsNeededMatch = candidate.skillsNeeded.some((s) =>
        request.userProfile.skillsToOffer.includes(s),
      );
      if (skillsToOfferMatch || skillsNeededMatch) {
        score += 25;
        reasons.push('Potential for skills exchange');
      }

      // Industry match
      if (
        candidate.industry &&
        candidate.industry === request.userProfile.industry
      ) {
        score += 10;
        reasons.push(`Same industry: ${candidate.industry}`);
      }

      return {
        userId: candidate.id,
        matchScore: Math.min(score, 100),
        reasons: reasons.length > 0 ? reasons : ['Nearby attendee at this event'],
        conversationStarters: this.generateFallbackConversationStarters(
          request.userProfile,
          candidate,
        ),
        potentialValue: 'Networking opportunity',
      };
    });

    // Sort by score and return top results
    const sorted = scored
      .filter((s) => s.matchScore > 0)
      .sort((a, b) => b.matchScore - a.matchScore)
      .slice(0, request.limit || 10);

    return { recommendations: sorted };
  }

  /**
   * Calculate goal compatibility score
   */
  private getGoalCompatibility(
    userGoals: Set<string>,
    candidateGoals: Set<string>,
  ): number {
    const compatiblePairs: [string, string][] = [
      ['HIRE', 'GET_HIRED'],
      ['GET_HIRED', 'HIRE'],
      ['MENTOR', 'GET_MENTORED'],
      ['GET_MENTORED', 'MENTOR'],
      ['SELL', 'BUY'],
      ['BUY', 'SELL'],
      ['FIND_PARTNERS', 'FIND_PARTNERS'],
      ['FIND_INVESTORS', 'NETWORK'],
    ];

    let matches = 0;
    for (const [userGoal, compatible] of compatiblePairs) {
      if (userGoals.has(userGoal) && candidateGoals.has(compatible)) {
        matches++;
      }
    }
    return matches;
  }

  /**
   * Generate basic conversation starters
   */
  private generateFallbackConversationStarters(
    user: UserProfileData,
    candidate: CandidateData,
  ): string[] {
    const starters: string[] = [];

    if (candidate.company) {
      starters.push(
        `I'd love to hear about your work at ${candidate.company}.`,
      );
    }

    const sharedInterests = user.interests.filter((i) =>
      candidate.interests.includes(i),
    );
    if (sharedInterests.length > 0) {
      starters.push(
        `I see we're both interested in ${sharedInterests[0]}. What's your take on it?`,
      );
    }

    if (candidate.githubTopLanguages?.length > 0) {
      starters.push(
        `I noticed you work with ${candidate.githubTopLanguages[0]}. What projects are you working on?`,
      );
    }

    return starters.slice(0, 2);
  }

  /**
   * Store recommendations in database
   */
  private async storeRecommendations(
    userId: string,
    eventId: string,
    recommendations: OracleRecommendationResponse['recommendations'],
  ): Promise<Recommendation[]> {
    const expiresAt = new Date();
    expiresAt.setHours(expiresAt.getHours() + this.RECOMMENDATION_TTL_HOURS);

    // Delete existing recommendations for this user/event
    await this.prisma.recommendation.deleteMany({
      where: { userId, eventId },
    });

    // Create new recommendations
    const created: Recommendation[] = [];
    for (const rec of recommendations) {
      const recommendation = await this.prisma.recommendation.create({
        data: {
          userId,
          eventId,
          recommendedUserId: rec.userId,
          matchScore: rec.matchScore,
          reasons: rec.reasons,
          conversationStarters: rec.conversationStarters,
          potentialValue: rec.potentialValue,
          expiresAt,
        },
      });
      created.push(recommendation);
    }

    return created;
  }

  /**
   * Get valid (non-expired) recommendations from DB
   */
  private async getValidDbRecommendations(
    userId: string,
    eventId: string,
  ): Promise<Recommendation[]> {
    return this.prisma.recommendation.findMany({
      where: {
        userId,
        eventId,
        expiresAt: { gt: new Date() },
      },
      orderBy: { matchScore: 'desc' },
    });
  }

  /**
   * Build response with user info for display
   */
  private async buildResponse(
    recommendations: Recommendation[],
    limit: number,
  ): Promise<RecommendationsResponseDto> {
    const userIds = recommendations.map((r) => r.recommendedUserId);

    // Get user details for display
    const users = await this.prisma.userReference.findMany({
      where: { id: { in: userIds } },
      select: {
        id: true,
        firstName: true,
        lastName: true,
        email: true, // Note: We won't include this in the response
        avatarUrl: true,
        linkedInUrl: true,
      },
    });

    // Get user profiles for additional info
    const profiles = await this.prisma.userProfile.findMany({
      where: { userId: { in: userIds } },
      select: {
        userId: true,
        industry: true,
        goals: true,
        linkedInUrl: true,
        githubUsername: true,
        twitterHandle: true,
      },
    });

    const userMap = new Map(users.map((u) => [u.id, u]));
    const profileMap = new Map(profiles.map((p) => [p.userId, p]));

    const enriched: RecommendationDto[] = recommendations
      .slice(0, limit)
      .map((rec) => {
        const user = userMap.get(rec.recommendedUserId);
        const profile = profileMap.get(rec.recommendedUserId);

        const userInfo: RecommendedUserInfo = {
          id: rec.recommendedUserId,
          name: user
            ? `${user.firstName || ''} ${user.lastName || ''}`.trim() || 'Attendee'
            : 'Attendee',
          avatarUrl: user?.avatarUrl || undefined,
          linkedInUrl: profile?.linkedInUrl || user?.linkedInUrl || undefined,
          githubUsername: profile?.githubUsername || undefined,
          twitterHandle: profile?.twitterHandle || undefined,
          industry: profile?.industry || undefined,
          goals: profile?.goals || [],
        };

        return {
          id: rec.id,
          userId: rec.userId,
          recommendedUserId: rec.recommendedUserId,
          matchScore: rec.matchScore,
          reasons: rec.reasons,
          conversationStarters: rec.conversationStarters,
          potentialValue: rec.potentialValue || undefined,
          generatedAt: rec.generatedAt,
          expiresAt: rec.expiresAt,
          viewed: rec.viewed,
          pinged: rec.pinged,
          connected: rec.connected,
          user: userInfo,
        };
      });

    return {
      recommendations: enriched,
      total: recommendations.length,
      hasMore: recommendations.length > limit,
      generatedAt: recommendations[0]?.generatedAt,
      expiresAt: recommendations[0]?.expiresAt,
    };
  }

  /**
   * Find or create UserReference, fetching from user-and-org-service if needed.
   */
  private async findOrCreateUserReference(userId: string): Promise<{
    id: string;
    firstName: string | null;
    lastName: string | null;
  } | null> {
    // Check if user exists locally
    const existingRef = await this.prisma.userReference.findUnique({
      where: { id: userId },
      select: { id: true, firstName: true, lastName: true },
    });

    if (existingRef && existingRef.firstName && existingRef.firstName !== 'Guest') {
      return existingRef;
    }

    // Try to fetch from user-and-org-service
    try {
      const userServiceUrl = this.configService.get<string>('USER_SERVICE_URL');
      const internalApiKey = this.configService.get<string>('INTERNAL_API_KEY');

      if (!userServiceUrl || !internalApiKey) {
        this.logger.warn('USER_SERVICE_URL or INTERNAL_API_KEY not configured');
        return existingRef; // Return existing (possibly placeholder) if available
      }

      const response = await firstValueFrom(
        this.httpService.get(`${userServiceUrl}/internal/users/${userId}`, {
          headers: { 'x-internal-api-key': internalApiKey },
          timeout: 5000,
        }),
      );

      const userData = response.data;
      if (userData) {
        // Upsert the user reference with real data
        const user = await this.prisma.userReference.upsert({
          where: { id: userId },
          update: {
            email: userData.email,
            firstName: userData.first_name || userData.firstName,
            lastName: userData.last_name || userData.lastName,
          },
          create: {
            id: userId,
            email: userData.email,
            firstName: userData.first_name || userData.firstName || 'User',
            lastName: userData.last_name || userData.lastName,
          },
          select: { id: true, firstName: true, lastName: true },
        });
        this.logger.debug(`Created/updated UserReference for ${userId}`);
        return user;
      }
    } catch (error) {
      this.logger.warn(`Failed to fetch user ${userId} from user service: ${error.message}`);
    }

    return existingRef; // Return existing (possibly null) if fetch failed
  }

  /**
   * Get user profile data for recommendation generation
   */
  private async getUserProfileData(
    userId: string,
  ): Promise<UserProfileData | null> {
    // Auto-create user reference if needed
    const user = await this.findOrCreateUserReference(userId);

    const profile = await this.prisma.userProfile.findUnique({
      where: { userId },
    });

    if (!user) return null;

    return {
      id: user.id,
      name: `${user.firstName || ''} ${user.lastName || ''}`.trim(),
      industry: profile?.industry || undefined,
      goals: profile?.goals || [],
      interests: profile?.interests || [],
      skillsToOffer: profile?.skillsToOffer || [],
      skillsNeeded: profile?.skillsNeeded || [],
      bio: profile?.bio || undefined,
      linkedInHeadline: profile?.linkedInHeadline || undefined,
      githubTopLanguages: profile?.githubTopLanguages || [],
      githubRepoCount: profile?.githubRepoCount || undefined,
      extractedSkills: profile?.extractedSkills || [],
    };
  }

  /**
   * Get candidate attendees at an event (excluding the user)
   */
  private async getEventCandidates(
    eventId: string,
    excludeUserId: string,
  ): Promise<CandidateData[]> {
    // Get users who have interacted at this event (messages, questions, etc.)
    // This is a simplified version - in production, you'd query event registrations
    const participants = await this.prisma.userReference.findMany({
      where: {
        id: { not: excludeUserId },
        // Users who have some activity in event sessions
        OR: [
          { messages: { some: { session: { eventId } } } },
          { questions: { some: { session: { eventId } } } },
          { pollVotes: { some: { poll: { session: { eventId } } } } },
        ],
      },
      select: {
        id: true,
        firstName: true,
        lastName: true,
        avatarUrl: true,
        linkedInUrl: true,
      },
      take: 100, // Limit initial candidates
    });

    const userIds = participants.map((p) => p.id);
    const profiles = await this.prisma.userProfile.findMany({
      where: { userId: { in: userIds } },
    });

    const profileMap = new Map(profiles.map((p) => [p.userId, p]));

    return participants.map((p) => {
      const profile = profileMap.get(p.id);
      return {
        id: p.id,
        name: `${p.firstName || ''} ${p.lastName || ''}`.trim(),
        avatarUrl: p.avatarUrl || undefined,
        linkedInUrl: profile?.linkedInUrl || p.linkedInUrl || undefined,
        githubUsername: profile?.githubUsername || undefined,
        twitterHandle: profile?.twitterHandle || undefined,
        industry: profile?.industry || undefined,
        goals: profile?.goals || [],
        interests: profile?.interests || [],
        skillsToOffer: profile?.skillsToOffer || [],
        skillsNeeded: profile?.skillsNeeded || [],
        bio: profile?.bio || undefined,
        linkedInHeadline: profile?.linkedInHeadline || undefined,
        githubTopLanguages: profile?.githubTopLanguages || [],
        githubRepoCount: profile?.githubRepoCount || undefined,
        extractedSkills: profile?.extractedSkills || [],
      };
    });
  }

  /**
   * Mark a recommendation as viewed
   * @param recommendationId - The recommendation ID
   * @param userId - The authenticated user ID
   * @param eventId - The event ID for validation (defense in depth)
   */
  async markViewed(
    recommendationId: string,
    userId: string,
    eventId: string,
  ): Promise<void> {
    const rec = await this.prisma.recommendation.findUnique({
      where: { id: recommendationId },
    });

    if (!rec) {
      this.logger.warn(`markViewed: Recommendation ${recommendationId} not found in DB`);
      throw new NotFoundException('Recommendation not found');
    }

    if (rec.userId !== userId) {
      this.logger.warn(
        `markViewed: userId mismatch for rec ${recommendationId} - ` +
        `JWT user: ${userId}, rec owner: ${rec.userId}`,
      );
      throw new NotFoundException('Recommendation not found');
    }

    // Validate eventId (defense in depth against URL manipulation)
    if (rec.eventId !== eventId) {
      throw new BadRequestException('Recommendation does not belong to this event');
    }

    await this.prisma.recommendation.update({
      where: { id: recommendationId },
      data: { viewed: true, viewedAt: new Date() },
    });

    // Invalidate cache
    await this.invalidateCache(userId, rec.eventId);
  }

  /**
   * Mark a recommendation as pinged
   * @param recommendationId - The recommendation ID
   * @param userId - The authenticated user ID
   * @param eventId - The event ID for validation (defense in depth)
   */
  async markPinged(
    recommendationId: string,
    userId: string,
    eventId: string,
  ): Promise<void> {
    const rec = await this.prisma.recommendation.findUnique({
      where: { id: recommendationId },
    });

    if (!rec) {
      this.logger.warn(`markPinged: Recommendation ${recommendationId} not found in DB`);
      throw new NotFoundException('Recommendation not found');
    }

    if (rec.userId !== userId) {
      this.logger.warn(
        `markPinged: userId mismatch for rec ${recommendationId} - ` +
        `JWT user: ${userId}, rec owner: ${rec.userId}`,
      );
      throw new NotFoundException('Recommendation not found');
    }

    // Validate eventId (defense in depth against URL manipulation)
    if (rec.eventId !== eventId) {
      throw new BadRequestException('Recommendation does not belong to this event');
    }

    await this.prisma.recommendation.update({
      where: { id: recommendationId },
      data: { pinged: true, pingedAt: new Date() },
    });

    // Invalidate cache
    await this.invalidateCache(userId, rec.eventId);
  }

  /**
   * Mark a recommendation as connected (user made a connection)
   * @param recommendationId - The recommendation ID
   * @param userId - The authenticated user ID
   * @param eventId - The event ID for validation (defense in depth)
   */
  async markConnected(
    recommendationId: string,
    userId: string,
    eventId: string,
  ): Promise<void> {
    const rec = await this.prisma.recommendation.findUnique({
      where: { id: recommendationId },
    });

    if (!rec) {
      this.logger.warn(`markConnected: Recommendation ${recommendationId} not found in DB`);
      throw new NotFoundException('Recommendation not found');
    }

    if (rec.userId !== userId) {
      this.logger.warn(
        `markConnected: userId mismatch for rec ${recommendationId} - ` +
        `JWT user: ${userId}, rec owner: ${rec.userId}`,
      );
      throw new NotFoundException('Recommendation not found');
    }

    // Validate eventId (defense in depth against URL manipulation)
    if (rec.eventId !== eventId) {
      throw new BadRequestException('Recommendation does not belong to this event');
    }

    await this.prisma.recommendation.update({
      where: { id: recommendationId },
      data: { connected: true, connectedAt: new Date() },
    });

    // Invalidate cache
    await this.invalidateCache(userId, rec.eventId);

    // Trigger Oracle AI to generate new suggestions based on this connection
    this.kafkaService
      .sendNetworkConnectionEvent({
        connectionId: recommendationId,
        eventId: rec.eventId,
        user1_id: userId,
        user2_id: rec.recommendedUserId,
      })
      .catch((err) =>
        this.logger.error('Failed to publish network connection event:', err),
      );
  }

  /**
   * Get cache key for recommendations
   */
  private getCacheKey(userId: string, eventId: string): string {
    return `recommendations:${eventId}:${userId}`;
  }

  /**
   * Invalidate cache for a user's recommendations
   */
  private async invalidateCache(
    userId: string,
    eventId: string,
  ): Promise<void> {
    const cacheKey = this.getCacheKey(userId, eventId);
    await this.redis.del(cacheKey);
  }

  /**
   * Trigger recommendations generation for a user (e.g., on event check-in)
   */
  async triggerRecommendationGeneration(
    userId: string,
    eventId: string,
  ): Promise<void> {
    this.logger.log(
      `Triggering recommendation generation for user ${userId} at event ${eventId}`,
    );

    // Generate in background (don't await)
    this.generateAndStoreRecommendations(userId, eventId, 10).catch((err) => {
      this.logger.error(`Background recommendation generation failed: ${err}`);
    });
  }

  /**
   * Get recommendation analytics for an event.
   *
   * Uses DB-level aggregation to avoid loading all records into memory.
   * Scales efficiently for large events with thousands of recommendations.
   */
  async getRecommendationAnalytics(eventId: string): Promise<{
    totalRecommendations: number;
    viewedCount: number;
    viewRate: number;
    pingedCount: number;
    pingRate: number;
    connectedCount: number;
    connectionRate: number;
    averageMatchScore: number;
  }> {
    // Run all queries in parallel for better performance
    const [totalCount, viewedCount, pingedCount, connectedCount, avgResult] =
      await Promise.all([
        // Total recommendations
        this.prisma.recommendation.count({
          where: { eventId },
        }),
        // Viewed count
        this.prisma.recommendation.count({
          where: { eventId, viewed: true },
        }),
        // Pinged count
        this.prisma.recommendation.count({
          where: { eventId, pinged: true },
        }),
        // Connected count
        this.prisma.recommendation.count({
          where: { eventId, connected: true },
        }),
        // Average match score
        this.prisma.recommendation.aggregate({
          where: { eventId },
          _avg: { matchScore: true },
        }),
      ]);

    const avgScore = avgResult._avg.matchScore ?? 0;

    return {
      totalRecommendations: totalCount,
      viewedCount,
      viewRate: totalCount > 0 ? (viewedCount / totalCount) * 100 : 0,
      pingedCount,
      pingRate: totalCount > 0 ? (pingedCount / totalCount) * 100 : 0,
      connectedCount,
      connectionRate: totalCount > 0 ? (connectedCount / totalCount) * 100 : 0,
      averageMatchScore: avgScore,
    };
  }

  /**
   * Get user's connections at an event.
   * Returns users where the recommendation has connected: true.
   *
   * @param userId - The authenticated user's ID
   * @param eventId - The event ID
   * @param limit - Maximum connections to return (default 50)
   */
  async getUserConnections(
    userId: string,
    eventId: string,
    limit: number = 50,
  ): Promise<ConnectionsResponseDto> {
    // Get recommendations where connected = true
    const connections = await this.prisma.recommendation.findMany({
      where: {
        userId,
        eventId,
        connected: true,
      },
      orderBy: { connectedAt: 'desc' },
      take: limit,
    });

    if (connections.length === 0) {
      return {
        connections: [],
        total: 0,
      };
    }

    // Get user info for the connected users
    const connectedUserIds = connections.map((c) => c.recommendedUserId);

    const users = await this.prisma.userReference.findMany({
      where: { id: { in: connectedUserIds } },
      select: {
        id: true,
        firstName: true,
        lastName: true,
        avatarUrl: true,
        linkedInUrl: true,
      },
    });

    // Get user profiles for additional social links
    const profiles = await this.prisma.userProfile.findMany({
      where: { userId: { in: connectedUserIds } },
      select: {
        userId: true,
        linkedInUrl: true,
        githubUsername: true,
        twitterHandle: true,
        company: true,
        currentRole: true,
      },
    });

    const userMap = new Map(users.map((u) => [u.id, u]));
    const profileMap = new Map(profiles.map((p) => [p.userId, p]));

    // Build response
    const enrichedConnections: ConnectionDto[] = connections.map((rec) => {
      const user = userMap.get(rec.recommendedUserId);
      const profile = profileMap.get(rec.recommendedUserId);

      const userInfo: ConnectedUserInfo = {
        id: rec.recommendedUserId,
        name: user
          ? `${user.firstName || ''} ${user.lastName || ''}`.trim() || 'Attendee'
          : 'Attendee',
        role: profile?.currentRole || undefined,
        company: profile?.company || undefined,
        avatarUrl: user?.avatarUrl || undefined,
        linkedInUrl: profile?.linkedInUrl || user?.linkedInUrl || undefined,
        githubUsername: profile?.githubUsername || undefined,
        twitterHandle: profile?.twitterHandle || undefined,
      };

      return {
        id: rec.id,
        connectedUserId: rec.recommendedUserId,
        connectedAt: rec.connectedAt || rec.generatedAt, // Fallback to generatedAt if connectedAt is null
        matchScore: rec.matchScore,
        reasons: rec.reasons,
        user: userInfo,
      };
    });

    // Get total count (in case we need pagination later)
    const totalCount = await this.prisma.recommendation.count({
      where: {
        userId,
        eventId,
        connected: true,
      },
    });

    return {
      connections: enrichedConnections,
      total: totalCount,
    };
  }
}
