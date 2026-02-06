// src/magic-link/magic-link.service.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { BadRequestException } from '@nestjs/common';
import { MagicLinkService } from './magic-link.service';
import { PrismaService } from 'src/prisma.service';
import { AuditService } from 'src/audit/audit.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';

describe('MagicLinkService', () => {
  let service: MagicLinkService;
  let jwtService: JwtService;
  let prismaService: PrismaService;
  let auditService: AuditService;
  let redisMock: Record<string, jest.Mock>;

  const mockUser = {
    id: 'user-123',
    email: 'test@example.com',
    first_name: 'John',
    last_name: 'Doe',
    tier: 'default',
    preferredLanguage: 'en',
    sponsorId: null,
    isTwoFactorEnabled: false,
    userType: 'ATTENDEE',
  };

  beforeEach(async () => {
    // Create Redis mock
    redisMock = {
      incr: jest.fn().mockResolvedValue(1),
      expire: jest.fn().mockResolvedValue(1),
      setex: jest.fn().mockResolvedValue('OK'),
      get: jest.fn().mockResolvedValue(null),
      del: jest.fn().mockResolvedValue(1),
      sadd: jest.fn().mockResolvedValue(1),
      smembers: jest.fn().mockResolvedValue([]),
      srem: jest.fn().mockResolvedValue(1),
      ttl: jest.fn().mockResolvedValue(3600),
    };

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        MagicLinkService,
        {
          provide: PrismaService,
          useValue: {
            user: {
              findUnique: jest.fn(),
            },
          },
        },
        {
          provide: JwtService,
          useValue: {
            signAsync: jest.fn().mockResolvedValue('mock-jwt-token'),
            verifyAsync: jest.fn(),
          },
        },
        {
          provide: ConfigService,
          useValue: {
            get: jest.fn((key: string) => {
              const config: Record<string, string> = {
                JWT_SECRET: 'test-secret',
                JWT_REFRESH_SECRET: 'test-refresh-secret',
                FRONTEND_URL: 'https://example.com',
              };
              return config[key];
            }),
          },
        },
        {
          provide: AuditService,
          useValue: {
            log: jest.fn().mockResolvedValue(undefined),
          },
        },
        {
          provide: REDIS_CLIENT,
          useValue: redisMock,
        },
      ],
    }).compile();

    service = module.get<MagicLinkService>(MagicLinkService);
    jwtService = module.get<JwtService>(JwtService);
    prismaService = module.get<PrismaService>(PrismaService);
    auditService = module.get<AuditService>(AuditService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('generateSessionJoinLink', () => {
    const generateParams = {
      userId: 'user-123',
      sessionId: 'session-456',
      eventId: 'event-789',
      registrationId: 'reg-abc',
      sessionEndTime: new Date(Date.now() + 3600000), // 1 hour from now
    };

    it('should generate a magic link successfully', async () => {
      jest.spyOn(prismaService.user, 'findUnique').mockResolvedValue(mockUser as any);

      const result = await service.generateSessionJoinLink(generateParams);

      expect(result).toHaveProperty('token');
      expect(result).toHaveProperty('url');
      expect(result).toHaveProperty('expiresAt');
      expect(result.url).toContain('https://example.com/auth/magic-link?token=');
      expect(redisMock.setex).toHaveBeenCalled();
      expect(redisMock.sadd).toHaveBeenCalled();
      expect(auditService.log).toHaveBeenCalledWith(
        expect.objectContaining({ action: 'MAGIC_LINK_GENERATED' }),
      );
    });

    it('should throw BadRequestException when user not found', async () => {
      jest.spyOn(prismaService.user, 'findUnique').mockResolvedValue(null);

      await expect(service.generateSessionJoinLink(generateParams)).rejects.toThrow(
        BadRequestException,
      );
    });

    it('should throw BadRequestException when rate limit exceeded', async () => {
      redisMock.incr.mockResolvedValue(11); // Exceed the 10 limit

      await expect(service.generateSessionJoinLink(generateParams)).rejects.toThrow(
        BadRequestException,
      );
      expect(auditService.log).toHaveBeenCalledWith(
        expect.objectContaining({ action: 'MAGIC_LINK_RATE_LIMIT_EXCEEDED' }),
      );
    });

    it('should set TTL on first rate limit request', async () => {
      redisMock.incr.mockResolvedValue(1);
      jest.spyOn(prismaService.user, 'findUnique').mockResolvedValue(mockUser as any);

      await service.generateSessionJoinLink(generateParams);

      expect(redisMock.expire).toHaveBeenCalledWith(`magic-link:rate:${generateParams.userId}`, 3600);
    });
  });

  describe('validateAndAuthenticate', () => {
    const mockPayload = {
      sub: 'user-123',
      jti: 'jti-abc',
      sessionId: 'session-456',
      eventId: 'event-789',
      registrationId: 'reg-abc',
      purpose: 'SESSION_JOIN' as const,
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 3600,
    };

    it('should validate and authenticate successfully', async () => {
      jest.spyOn(jwtService, 'verifyAsync').mockResolvedValue(mockPayload);
      redisMock.get.mockResolvedValue(JSON.stringify({ used: false, userId: 'user-123' }));
      jest.spyOn(prismaService.user, 'findUnique').mockResolvedValue(mockUser as any);

      const result = await service.validateAndAuthenticate('valid-token');

      expect(result.valid).toBe(true);
      expect(result.accessToken).toBeDefined();
      expect(result.refreshToken).toBeDefined();
      expect(result.user).toEqual({
        id: mockUser.id,
        email: mockUser.email,
        firstName: mockUser.first_name,
        lastName: mockUser.last_name,
      });
      expect(result.redirect).toBeDefined();
      expect(auditService.log).toHaveBeenCalledWith(
        expect.objectContaining({ action: 'MAGIC_LINK_AUTH_SUCCESS' }),
      );
    });

    it('should return TOKEN_INVALID for invalid JWT', async () => {
      jest.spyOn(jwtService, 'verifyAsync').mockRejectedValue(new Error('Invalid token'));

      const result = await service.validateAndAuthenticate('invalid-token');

      expect(result.valid).toBe(false);
      expect(result.error).toBe('TOKEN_INVALID');
    });

    it('should return TOKEN_EXPIRED when token not in Redis', async () => {
      jest.spyOn(jwtService, 'verifyAsync').mockResolvedValue(mockPayload);
      redisMock.get.mockResolvedValue(null);

      const result = await service.validateAndAuthenticate('expired-token');

      expect(result.valid).toBe(false);
      expect(result.error).toBe('TOKEN_EXPIRED');
    });

    it('should return TOKEN_USED when token already used', async () => {
      jest.spyOn(jwtService, 'verifyAsync').mockResolvedValue(mockPayload);
      redisMock.get.mockResolvedValue(JSON.stringify({ used: true, userId: 'user-123' }));

      const result = await service.validateAndAuthenticate('used-token');

      expect(result.valid).toBe(false);
      expect(result.error).toBe('TOKEN_USED');
      expect(auditService.log).toHaveBeenCalledWith(
        expect.objectContaining({ action: 'MAGIC_LINK_REUSE_ATTEMPT' }),
      );
    });

    it('should return USER_NOT_FOUND when user does not exist', async () => {
      jest.spyOn(jwtService, 'verifyAsync').mockResolvedValue(mockPayload);
      redisMock.get.mockResolvedValue(JSON.stringify({ used: false, userId: 'user-123' }));
      jest.spyOn(prismaService.user, 'findUnique').mockResolvedValue(null);

      const result = await service.validateAndAuthenticate('valid-token');

      expect(result.valid).toBe(false);
      expect(result.error).toBe('USER_NOT_FOUND');
    });

    it('should return TOKEN_INVALID for wrong purpose', async () => {
      const wrongPurposePayload = { ...mockPayload, purpose: 'WRONG_PURPOSE' };
      jest.spyOn(jwtService, 'verifyAsync').mockResolvedValue(wrongPurposePayload as any);

      const result = await service.validateAndAuthenticate('wrong-purpose-token');

      expect(result.valid).toBe(false);
      expect(result.error).toBe('TOKEN_INVALID');
    });

    it('should mark token as used after successful validation', async () => {
      jest.spyOn(jwtService, 'verifyAsync').mockResolvedValue(mockPayload);
      redisMock.get.mockResolvedValue(JSON.stringify({ used: false, userId: 'user-123' }));
      redisMock.ttl.mockResolvedValue(3600);
      jest.spyOn(prismaService.user, 'findUnique').mockResolvedValue(mockUser as any);

      await service.validateAndAuthenticate('valid-token');

      expect(redisMock.setex).toHaveBeenCalledWith(
        `magic-link:${mockPayload.jti}`,
        3600,
        expect.stringContaining('"used":true'),
      );
    });
  });

  describe('revoke', () => {
    it('should revoke a token successfully', async () => {
      const tokenData = { userId: 'user-123', registrationId: 'reg-abc' };
      redisMock.get.mockResolvedValue(JSON.stringify(tokenData));

      await service.revoke('jti-abc');

      expect(redisMock.del).toHaveBeenCalledWith('magic-link:jti-abc');
      expect(redisMock.srem).toHaveBeenCalledWith('magic-link:reg:reg-abc', 'jti-abc');
      expect(auditService.log).toHaveBeenCalledWith(
        expect.objectContaining({ action: 'MAGIC_LINK_REVOKED' }),
      );
    });

    it('should do nothing for non-existent token', async () => {
      redisMock.get.mockResolvedValue(null);

      await service.revoke('non-existent-jti');

      expect(redisMock.del).not.toHaveBeenCalled();
      expect(auditService.log).not.toHaveBeenCalled();
    });
  });

  describe('revokeAllForRegistration', () => {
    it('should revoke all tokens for a registration', async () => {
      redisMock.smembers.mockResolvedValue(['jti-1', 'jti-2', 'jti-3']);

      await service.revokeAllForRegistration('reg-abc');

      expect(redisMock.del).toHaveBeenCalledWith(
        'magic-link:jti-1',
        'magic-link:jti-2',
        'magic-link:jti-3',
      );
      expect(redisMock.del).toHaveBeenCalledWith('magic-link:reg:reg-abc');
      expect(auditService.log).toHaveBeenCalledWith(
        expect.objectContaining({
          action: 'MAGIC_LINK_BULK_REVOKED',
          details: { registrationId: 'reg-abc', count: 3 },
        }),
      );
    });

    it('should do nothing when no tokens for registration', async () => {
      redisMock.smembers.mockResolvedValue([]);

      await service.revokeAllForRegistration('reg-abc');

      expect(redisMock.del).not.toHaveBeenCalled();
      expect(auditService.log).not.toHaveBeenCalled();
    });
  });

  describe('checkTokenStatus', () => {
    it('should return valid status for unused token', async () => {
      redisMock.get.mockResolvedValue(JSON.stringify({ used: false }));
      redisMock.ttl.mockResolvedValue(3600);

      const result = await service.checkTokenStatus('jti-abc');

      expect(result).toEqual({ valid: true, used: false, expiresIn: 3600 });
    });

    it('should return invalid status for used token', async () => {
      redisMock.get.mockResolvedValue(JSON.stringify({ used: true }));
      redisMock.ttl.mockResolvedValue(3600);

      const result = await service.checkTokenStatus('jti-abc');

      expect(result).toEqual({ valid: false, used: true, expiresIn: 3600 });
    });

    it('should return invalid status for expired token', async () => {
      redisMock.get.mockResolvedValue(null);
      redisMock.ttl.mockResolvedValue(-2);

      const result = await service.checkTokenStatus('jti-abc');

      expect(result).toEqual({ valid: false, used: false, expiresIn: 0 });
    });
  });
});
