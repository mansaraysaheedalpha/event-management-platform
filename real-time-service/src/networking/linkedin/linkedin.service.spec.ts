//src/networking/linkedin/linkedin.service.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { LinkedInService } from './linkedin.service';
import { PrismaService } from 'src/prisma.service';
import { ConfigService } from '@nestjs/config';
import { UnauthorizedException, BadRequestException } from '@nestjs/common';

// Mock global fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

const mockPrisma = {
  userReference: {
    update: jest.fn(),
    findUnique: jest.fn(),
  },
  connection: {
    findMany: jest.fn(),
  },
};

const mockConfigService = {
  get: jest.fn((key: string) => {
    const config: Record<string, string> = {
      LINKEDIN_CLIENT_ID: 'test-client-id',
      LINKEDIN_CLIENT_SECRET: 'test-client-secret',
      LINKEDIN_REDIRECT_URI: 'http://localhost:3000/api/auth/linkedin/callback',
    };
    return config[key];
  }),
};

describe('LinkedInService', () => {
  let service: LinkedInService;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        LinkedInService,
        { provide: PrismaService, useValue: mockPrisma },
        { provide: ConfigService, useValue: mockConfigService },
      ],
    }).compile();
    service = module.get<LinkedInService>(LinkedInService);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  describe('getAuthorizationUrl', () => {
    it('should generate correct LinkedIn OAuth URL', () => {
      const state = 'random-state-123';
      const url = service.getAuthorizationUrl(state);

      expect(url).toContain('https://www.linkedin.com/oauth/v2/authorization');
      expect(url).toContain('client_id=test-client-id');
      expect(url).toContain('state=random-state-123');
      expect(url).toContain('response_type=code');
      expect(url).toContain('scope=');
    });
  });

  describe('exchangeCodeForToken', () => {
    it('should exchange code for tokens successfully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: 'access-token-123',
          refresh_token: 'refresh-token-456',
          expires_in: 3600,
        }),
      });

      const tokens = await service.exchangeCodeForToken('auth-code');

      expect(tokens.accessToken).toBe('access-token-123');
      expect(tokens.refreshToken).toBe('refresh-token-456');
      expect(tokens.expiresIn).toBe(3600);
      expect(mockFetch).toHaveBeenCalledWith(
        'https://www.linkedin.com/oauth/v2/accessToken',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        }),
      );
    });

    it('should throw UnauthorizedException on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        text: async () => 'Invalid code',
      });

      await expect(service.exchangeCodeForToken('invalid-code')).rejects.toThrow(
        UnauthorizedException,
      );
    });
  });

  describe('fetchProfile', () => {
    it('should fetch and parse LinkedIn profile', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          sub: 'linkedin-user-123',
          given_name: 'John',
          family_name: 'Doe',
          email: 'john@example.com',
          headline: 'Software Engineer',
          picture: 'https://linkedin.com/photo.jpg',
        }),
      });

      const profile = await service.fetchProfile('access-token');

      expect(profile.id).toBe('linkedin-user-123');
      expect(profile.firstName).toBe('John');
      expect(profile.lastName).toBe('Doe');
      expect(profile.email).toBe('john@example.com');
      expect(profile.headline).toBe('Software Engineer');
      expect(profile.pictureUrl).toBe('https://linkedin.com/photo.jpg');
    });

    it('should throw BadRequestException on fetch failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        text: async () => 'Invalid token',
      });

      await expect(service.fetchProfile('invalid-token')).rejects.toThrow(
        BadRequestException,
      );
    });
  });

  describe('connectLinkedIn', () => {
    it('should connect LinkedIn and update user', async () => {
      // Mock token exchange
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: 'access-token',
          refresh_token: 'refresh-token',
          expires_in: 3600,
        }),
      });

      // Mock profile fetch
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          sub: 'li-123',
          given_name: 'Jane',
          family_name: 'Smith',
          email: 'jane@example.com',
        }),
      });

      mockPrisma.userReference.update.mockResolvedValue({});

      const profile = await service.connectLinkedIn('user-1', 'auth-code');

      expect(profile.id).toBe('li-123');
      expect(profile.firstName).toBe('Jane');
      expect(mockPrisma.userReference.update).toHaveBeenCalledWith({
        where: { id: 'user-1' },
        data: expect.objectContaining({
          linkedInId: 'li-123',
          linkedInAccessToken: 'access-token',
          linkedInRefreshToken: 'refresh-token',
        }),
      });
    });
  });

  describe('disconnectLinkedIn', () => {
    it('should clear all LinkedIn fields', async () => {
      mockPrisma.userReference.update.mockResolvedValue({});

      await service.disconnectLinkedIn('user-1');

      expect(mockPrisma.userReference.update).toHaveBeenCalledWith({
        where: { id: 'user-1' },
        data: {
          linkedInId: null,
          linkedInUrl: null,
          linkedInHeadline: null,
          linkedInAccessToken: null,
          linkedInRefreshToken: null,
          linkedInTokenExpiresAt: null,
        },
      });
    });
  });

  describe('isLinkedInConnected', () => {
    it('should return true if user has LinkedIn connected', async () => {
      mockPrisma.userReference.findUnique.mockResolvedValue({
        linkedInId: 'li-123',
        linkedInAccessToken: 'token',
      });

      const connected = await service.isLinkedInConnected('user-1');

      expect(connected).toBe(true);
    });

    it('should return false if user has no LinkedIn', async () => {
      mockPrisma.userReference.findUnique.mockResolvedValue({
        linkedInId: null,
        linkedInAccessToken: null,
      });

      const connected = await service.isLinkedInConnected('user-1');

      expect(connected).toBe(false);
    });

    it('should return false if user not found', async () => {
      mockPrisma.userReference.findUnique.mockResolvedValue(null);

      const connected = await service.isLinkedInConnected('non-existent');

      expect(connected).toBe(false);
    });
  });

  describe('generateConnectionMessage', () => {
    it('should generate message with shared context', () => {
      const message = service.generateConnectionMessage(
        'John',
        'TechConf 2026',
        'are interested in AI',
      );

      expect(message).toContain('John');
      expect(message).toContain('TechConf 2026');
      expect(message).toContain('are interested in AI');
    });

    it('should generate default message without context', () => {
      const message = service.generateConnectionMessage('John', 'TechConf 2026');

      expect(message).toContain('John');
      expect(message).toContain('TechConf 2026');
      expect(message).toContain('great meeting you');
    });
  });

  describe('getLinkedInSuggestions', () => {
    it('should return suggestions for connections with LinkedIn', async () => {
      mockPrisma.connection.findMany.mockResolvedValue([
        {
          userAId: 'user-1',
          userBId: 'user-2',
          userA: { id: 'user-1', firstName: 'Me', lastName: 'User', linkedInId: null, linkedInUrl: null, linkedInHeadline: null },
          userB: { id: 'user-2', firstName: 'John', lastName: 'Doe', linkedInId: 'li-123', linkedInUrl: 'https://linkedin.com/in/johndoe', linkedInHeadline: 'Engineer' },
          contexts: [{ contextValue: 'AI workshop' }],
        },
        {
          userAId: 'user-1',
          userBId: 'user-3',
          userA: { id: 'user-1', firstName: 'Me', lastName: 'User', linkedInId: null, linkedInUrl: null, linkedInHeadline: null },
          userB: { id: 'user-3', firstName: 'Jane', lastName: 'Smith', linkedInId: null, linkedInUrl: null, linkedInHeadline: null },
          contexts: [],
        },
      ]);

      const suggestions = await service.getLinkedInSuggestions('user-1', 'event-1');

      expect(suggestions).toHaveLength(1); // Only user-2 has LinkedIn
      expect(suggestions[0].userId).toBe('user-2');
      expect(suggestions[0].linkedInUrl).toBe('https://linkedin.com/in/johndoe');
      expect(suggestions[0].headline).toBe('Engineer');
    });

    it('should return empty array if no connections have LinkedIn', async () => {
      mockPrisma.connection.findMany.mockResolvedValue([
        {
          userAId: 'user-1',
          userBId: 'user-2',
          userA: { id: 'user-1', firstName: 'Me', lastName: 'User', linkedInId: null, linkedInUrl: null, linkedInHeadline: null },
          userB: { id: 'user-2', firstName: 'John', lastName: 'Doe', linkedInId: null, linkedInUrl: null, linkedInHeadline: null },
          contexts: [],
        },
      ]);

      const suggestions = await service.getLinkedInSuggestions('user-1', 'event-1');

      expect(suggestions).toHaveLength(0);
    });
  });

  describe('refreshTokenIfNeeded', () => {
    it('should return existing token if not expired', async () => {
      mockPrisma.userReference.findUnique.mockResolvedValue({
        linkedInAccessToken: 'valid-token',
        linkedInRefreshToken: 'refresh-token',
        linkedInTokenExpiresAt: new Date(Date.now() + 60 * 60 * 1000), // 1 hour from now
      });

      const token = await service.refreshTokenIfNeeded('user-1');

      expect(token).toBe('valid-token');
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('should refresh token if expired', async () => {
      mockPrisma.userReference.findUnique.mockResolvedValue({
        linkedInAccessToken: 'expired-token',
        linkedInRefreshToken: 'refresh-token',
        linkedInTokenExpiresAt: new Date(Date.now() - 1000), // Expired
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: 'new-access-token',
          refresh_token: 'new-refresh-token',
          expires_in: 3600,
        }),
      });

      mockPrisma.userReference.update.mockResolvedValue({});

      const token = await service.refreshTokenIfNeeded('user-1');

      expect(token).toBe('new-access-token');
      expect(mockPrisma.userReference.update).toHaveBeenCalledWith({
        where: { id: 'user-1' },
        data: expect.objectContaining({
          linkedInAccessToken: 'new-access-token',
        }),
      });
    });

    it('should return null if no refresh token available', async () => {
      mockPrisma.userReference.findUnique.mockResolvedValue({
        linkedInAccessToken: 'expired-token',
        linkedInRefreshToken: null,
        linkedInTokenExpiresAt: new Date(Date.now() - 1000), // Expired
      });

      const token = await service.refreshTokenIfNeeded('user-1');

      expect(token).toBeNull();
    });
  });
});
