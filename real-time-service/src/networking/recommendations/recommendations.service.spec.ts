//src/networking/recommendations/recommendations.service.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { RecommendationsService } from './recommendations.service';
import { PrismaService } from 'src/prisma.service';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { of, throwError } from 'rxjs';
import { NotFoundException } from '@nestjs/common';

describe('RecommendationsService', () => {
  let service: RecommendationsService;
  let prisma: PrismaService;
  let httpService: HttpService;
  let redis: any;

  const mockUserId = 'user-123';
  const mockEventId = 'event-456';
  const mockRecommendedUserId = 'user-789';

  const mockUserReference = {
    id: mockUserId,
    firstName: 'John',
    lastName: 'Doe',
    email: 'john@example.com',
    avatarUrl: 'https://example.com/avatar.jpg',
    linkedInUrl: 'https://linkedin.com/in/johndoe',
  };

  const mockUserProfile = {
    id: 'profile-1',
    userId: mockUserId,
    interests: ['AI', 'ML'],
    goals: ['NETWORK', 'LEARN'],
    industry: 'Technology',
    skillsToOffer: ['Python', 'Machine Learning'],
    skillsNeeded: ['Product Management'],
    bio: 'Software engineer passionate about AI',
    linkedInHeadline: 'Senior AI Engineer',
    githubTopLanguages: ['Python', 'TypeScript'],
    githubRepoCount: 25,
    extractedSkills: ['TensorFlow', 'PyTorch'],
    enrichmentStatus: 'COMPLETED',
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  const mockRecommendation = {
    id: 'rec-1',
    userId: mockUserId,
    eventId: mockEventId,
    recommendedUserId: mockRecommendedUserId,
    matchScore: 85,
    reasons: ['Shared interest in AI', 'Both looking to network'],
    conversationStarters: ['What AI projects are you working on?'],
    potentialValue: 'Knowledge exchange',
    generatedAt: new Date(),
    expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000),
    viewed: false,
    viewedAt: null,
    pinged: false,
    pingedAt: null,
    connected: false,
    connectedAt: null,
  };

  const mockOracleResponse = {
    data: {
      recommendations: [
        {
          userId: mockRecommendedUserId,
          matchScore: 85,
          reasons: ['Shared interest in AI', 'Both looking to network'],
          conversationStarters: ['What AI projects are you working on?'],
          potentialValue: 'Knowledge exchange',
        },
      ],
    },
  };

  beforeEach(async () => {
    const mockRedis = {
      get: jest.fn().mockResolvedValue(null),
      setex: jest.fn().mockResolvedValue('OK'),
      del: jest.fn().mockResolvedValue(1),
    };

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        RecommendationsService,
        {
          provide: PrismaService,
          useValue: {
            recommendation: {
              findMany: jest.fn(),
              findUnique: jest.fn(),
              create: jest.fn(),
              update: jest.fn(),
              deleteMany: jest.fn(),
            },
            userReference: {
              findUnique: jest.fn(),
              findMany: jest.fn(),
            },
            userProfile: {
              findUnique: jest.fn(),
              findMany: jest.fn(),
            },
          },
        },
        {
          provide: HttpService,
          useValue: {
            post: jest.fn(),
          },
        },
        {
          provide: ConfigService,
          useValue: {
            get: jest.fn().mockReturnValue('http://localhost:8000'),
          },
        },
        {
          provide: REDIS_CLIENT,
          useValue: mockRedis,
        },
      ],
    }).compile();

    service = module.get<RecommendationsService>(RecommendationsService);
    prisma = module.get<PrismaService>(PrismaService);
    httpService = module.get<HttpService>(HttpService);
    redis = module.get(REDIS_CLIENT);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('getRecommendations', () => {
    it('should return cached recommendations from Redis', async () => {
      const cachedResponse = {
        recommendations: [
          {
            ...mockRecommendation,
            user: {
              id: mockRecommendedUserId,
              name: 'Jane Smith',
              avatarUrl: null,
            },
          },
        ],
        total: 1,
        hasMore: false,
      };

      redis.get.mockResolvedValue(JSON.stringify(cachedResponse));

      const result = await service.getRecommendations(mockUserId, mockEventId);

      expect(redis.get).toHaveBeenCalledWith(
        `recommendations:${mockEventId}:${mockUserId}`,
      );
      expect(result).toEqual(cachedResponse);
    });

    it('should return valid recommendations from DB when not in cache', async () => {
      // No cache hit
      redis.get.mockResolvedValue(null);

      // Valid recommendations in DB
      jest
        .spyOn(prisma.recommendation, 'findMany')
        .mockResolvedValue([mockRecommendation] as any);

      // User details for building response
      jest.spyOn(prisma.userReference, 'findMany').mockResolvedValue([
        {
          id: mockRecommendedUserId,
          firstName: 'Jane',
          lastName: 'Smith',
          email: 'jane@example.com',
          avatarUrl: null,
          linkedInUrl: null,
        },
      ] as any);

      jest.spyOn(prisma.userProfile, 'findMany').mockResolvedValue([]);

      const result = await service.getRecommendations(mockUserId, mockEventId);

      expect(result.recommendations).toHaveLength(1);
      expect(result.recommendations[0].matchScore).toBe(85);
      expect(result.recommendations[0].user.name).toBe('Jane Smith');

      // Should cache the result
      expect(redis.setex).toHaveBeenCalled();
    });

    it('should generate new recommendations when DB is empty', async () => {
      // No cache hit
      redis.get.mockResolvedValue(null);

      // No valid recommendations in DB
      jest.spyOn(prisma.recommendation, 'findMany').mockResolvedValue([]);

      // User profile for generation
      jest.spyOn(prisma.userReference, 'findUnique').mockResolvedValue(mockUserReference as any);
      jest.spyOn(prisma.userProfile, 'findUnique').mockResolvedValue(mockUserProfile as any);

      // Event candidates
      jest.spyOn(prisma.userReference, 'findMany').mockResolvedValue([
        {
          id: mockRecommendedUserId,
          firstName: 'Jane',
          lastName: 'Smith',
          email: 'jane@example.com',
          avatarUrl: null,
          linkedInUrl: null,
        },
      ] as any);
      jest.spyOn(prisma.userProfile, 'findMany').mockResolvedValue([
        {
          userId: mockRecommendedUserId,
          interests: ['AI'],
          goals: ['NETWORK'],
          industry: 'Technology',
          skillsToOffer: ['Product Management'],
          skillsNeeded: ['Python'],
        },
      ] as any);

      // Mock oracle service call
      jest.spyOn(httpService, 'post').mockReturnValue(of(mockOracleResponse) as any);

      // Mock DB operations for storing
      jest.spyOn(prisma.recommendation, 'deleteMany').mockResolvedValue({ count: 0 });
      jest.spyOn(prisma.recommendation, 'create').mockResolvedValue(mockRecommendation as any);

      const result = await service.getRecommendations(mockUserId, mockEventId);

      expect(httpService.post).toHaveBeenCalled();
      expect(prisma.recommendation.create).toHaveBeenCalled();
      expect(result.recommendations).toBeDefined();
    });

    it('should use fallback recommendations when oracle service fails', async () => {
      // No cache hit
      redis.get.mockResolvedValue(null);

      // No valid recommendations in DB
      jest.spyOn(prisma.recommendation, 'findMany').mockResolvedValue([]);

      // User profile for generation
      jest.spyOn(prisma.userReference, 'findUnique').mockResolvedValue(mockUserReference as any);
      jest.spyOn(prisma.userProfile, 'findUnique').mockResolvedValue(mockUserProfile as any);

      // Event candidates
      jest.spyOn(prisma.userReference, 'findMany').mockResolvedValue([
        {
          id: mockRecommendedUserId,
          firstName: 'Jane',
          lastName: 'Smith',
          email: 'jane@example.com',
          avatarUrl: null,
          linkedInUrl: null,
        },
      ] as any);
      jest.spyOn(prisma.userProfile, 'findMany').mockResolvedValue([
        {
          userId: mockRecommendedUserId,
          interests: ['AI', 'ML'],
          goals: ['NETWORK'],
          industry: 'Technology',
          skillsToOffer: ['Product Management'],
          skillsNeeded: ['Python'],
        },
      ] as any);

      // Oracle service fails
      jest.spyOn(httpService, 'post').mockReturnValue(
        throwError(() => new Error('Oracle service unavailable')),
      );

      // Mock DB operations
      jest.spyOn(prisma.recommendation, 'deleteMany').mockResolvedValue({ count: 0 });
      jest.spyOn(prisma.recommendation, 'create').mockResolvedValue(mockRecommendation as any);

      const result = await service.getRecommendations(mockUserId, mockEventId);

      // Should still return recommendations using fallback logic
      expect(result.recommendations).toBeDefined();
    });

    it('should force refresh when refresh option is true', async () => {
      // User profile
      jest.spyOn(prisma.userReference, 'findUnique').mockResolvedValue(mockUserReference as any);
      jest.spyOn(prisma.userProfile, 'findUnique').mockResolvedValue(mockUserProfile as any);

      // Event candidates
      jest.spyOn(prisma.userReference, 'findMany').mockResolvedValue([
        {
          id: mockRecommendedUserId,
          firstName: 'Jane',
          lastName: 'Smith',
          email: 'jane@example.com',
          avatarUrl: null,
          linkedInUrl: null,
        },
      ] as any);
      jest.spyOn(prisma.userProfile, 'findMany').mockResolvedValue([]);

      // Mock oracle service
      jest.spyOn(httpService, 'post').mockReturnValue(of(mockOracleResponse) as any);

      // Mock DB operations
      jest.spyOn(prisma.recommendation, 'deleteMany').mockResolvedValue({ count: 1 });
      jest.spyOn(prisma.recommendation, 'create').mockResolvedValue(mockRecommendation as any);

      await service.getRecommendations(mockUserId, mockEventId, { refresh: true });

      // Should NOT check cache when refresh is true
      expect(redis.get).not.toHaveBeenCalled();

      // Should delete old recommendations
      expect(prisma.recommendation.deleteMany).toHaveBeenCalledWith({
        where: { userId: mockUserId, eventId: mockEventId },
      });
    });
  });

  describe('markViewed', () => {
    it('should mark a recommendation as viewed', async () => {
      jest
        .spyOn(prisma.recommendation, 'findUnique')
        .mockResolvedValue(mockRecommendation as any);
      jest
        .spyOn(prisma.recommendation, 'update')
        .mockResolvedValue({ ...mockRecommendation, viewed: true } as any);

      await service.markViewed('rec-1', mockUserId, mockEventId);

      expect(prisma.recommendation.update).toHaveBeenCalledWith({
        where: { id: 'rec-1' },
        data: { viewed: true, viewedAt: expect.any(Date) },
      });

      // Should invalidate cache
      expect(redis.del).toHaveBeenCalled();
    });

    it('should throw NotFoundException for invalid recommendation', async () => {
      jest.spyOn(prisma.recommendation, 'findUnique').mockResolvedValue(null);

      await expect(service.markViewed('invalid-id', mockUserId, mockEventId)).rejects.toThrow(
        NotFoundException,
      );
    });

    it('should throw NotFoundException if user does not own recommendation', async () => {
      jest.spyOn(prisma.recommendation, 'findUnique').mockResolvedValue({
        ...mockRecommendation,
        userId: 'different-user',
      } as any);

      await expect(service.markViewed('rec-1', mockUserId, mockEventId)).rejects.toThrow(
        NotFoundException,
      );
    });
  });

  describe('markPinged', () => {
    it('should mark a recommendation as pinged', async () => {
      jest
        .spyOn(prisma.recommendation, 'findUnique')
        .mockResolvedValue(mockRecommendation as any);
      jest
        .spyOn(prisma.recommendation, 'update')
        .mockResolvedValue({ ...mockRecommendation, pinged: true } as any);

      await service.markPinged('rec-1', mockUserId, mockEventId);

      expect(prisma.recommendation.update).toHaveBeenCalledWith({
        where: { id: 'rec-1' },
        data: { pinged: true, pingedAt: expect.any(Date) },
      });
    });
  });

  describe('markConnected', () => {
    it('should mark a recommendation as connected', async () => {
      jest
        .spyOn(prisma.recommendation, 'findUnique')
        .mockResolvedValue(mockRecommendation as any);
      jest
        .spyOn(prisma.recommendation, 'update')
        .mockResolvedValue({ ...mockRecommendation, connected: true } as any);

      await service.markConnected('rec-1', mockUserId, mockEventId);

      expect(prisma.recommendation.update).toHaveBeenCalledWith({
        where: { id: 'rec-1' },
        data: { connected: true, connectedAt: expect.any(Date) },
      });
    });
  });

  describe('getRecommendationAnalytics', () => {
    it('should return analytics for an event', async () => {
      jest.spyOn(prisma.recommendation, 'findMany').mockResolvedValue([
        { ...mockRecommendation, viewed: true, pinged: true, connected: false },
        { ...mockRecommendation, id: 'rec-2', viewed: true, pinged: false, connected: false },
        { ...mockRecommendation, id: 'rec-3', viewed: false, pinged: false, connected: false },
      ] as any);

      const analytics = await service.getRecommendationAnalytics(mockEventId);

      expect(analytics.totalRecommendations).toBe(3);
      expect(analytics.viewedCount).toBe(2);
      expect(analytics.viewRate).toBeCloseTo(66.67, 1);
      expect(analytics.pingedCount).toBe(1);
      expect(analytics.pingRate).toBeCloseTo(33.33, 1);
      expect(analytics.connectedCount).toBe(0);
      expect(analytics.connectionRate).toBe(0);
      expect(analytics.averageMatchScore).toBe(85);
    });

    it('should handle empty results', async () => {
      jest.spyOn(prisma.recommendation, 'findMany').mockResolvedValue([]);

      const analytics = await service.getRecommendationAnalytics(mockEventId);

      expect(analytics.totalRecommendations).toBe(0);
      expect(analytics.viewRate).toBe(0);
      expect(analytics.averageMatchScore).toBe(0);
    });
  });
});
