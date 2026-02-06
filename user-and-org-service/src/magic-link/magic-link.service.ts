// src/magic-link/magic-link.service.ts
import {
  Injectable,
  Inject,
  UnauthorizedException,
  BadRequestException,
  Logger,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from 'src/prisma.service';
import { AuditService } from 'src/audit/audit.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { Redis } from 'ioredis';
import { randomBytes } from 'crypto';

// Magic Link JWT payload structure
export interface MagicLinkPayload {
  sub: string;           // User ID
  jti: string;           // Unique token ID
  sessionId: string;     // Target session
  eventId: string;       // Parent event
  registrationId: string;// Registration record
  purpose: 'SESSION_JOIN';
  iat: number;           // Issued at
  exp: number;           // Expiry (session end + 30min)
}

// Error types for magic link validation
export type MagicLinkError =
  | 'TOKEN_EXPIRED'
  | 'TOKEN_REVOKED'
  | 'TOKEN_INVALID'
  | 'TOKEN_USED'
  | 'SESSION_ENDED'
  | 'RATE_LIMIT_EXCEEDED'
  | 'USER_NOT_FOUND';

// Validation result
export interface MagicLinkValidationResult {
  valid: boolean;
  accessToken?: string;
  refreshToken?: string;
  user?: {
    id: string;
    email: string;
    firstName: string;
    lastName: string;
  };
  redirect?: {
    sessionId: string;
    eventId: string;
    url: string;
  };
  error?: MagicLinkError;
}

// Generation result
export interface MagicLinkGenerationResult {
  token: string;
  url: string;
  expiresAt: Date;
}

@Injectable()
export class MagicLinkService {
  private readonly logger = new Logger(MagicLinkService.name);
  private readonly RATE_LIMIT_MAX = 10; // Max tokens per user per hour
  private readonly RATE_LIMIT_WINDOW = 3600; // 1 hour in seconds
  private readonly MAX_EXPIRY_OFFSET = 30 * 60 * 1000; // 30 minutes in ms

  constructor(
    private readonly prisma: PrismaService,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
    private readonly auditService: AuditService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
  ) {}

  /**
   * Generate a magic link for session joining
   */
  async generateSessionJoinLink(params: {
    userId: string;
    sessionId: string;
    eventId: string;
    registrationId: string;
    sessionEndTime: Date;
  }): Promise<MagicLinkGenerationResult> {
    const { userId, sessionId, eventId, registrationId, sessionEndTime } = params;

    // Check rate limit
    const rateLimitKey = `magic-link:rate:${userId}`;
    const currentCount = await this.redis.incr(rateLimitKey);

    if (currentCount === 1) {
      // First request in window - set TTL
      await this.redis.expire(rateLimitKey, this.RATE_LIMIT_WINDOW);
    }

    if (currentCount > this.RATE_LIMIT_MAX) {
      this.logger.warn(`Rate limit exceeded for user ${userId}`);
      await this.auditService.log({
        action: 'MAGIC_LINK_RATE_LIMIT_EXCEEDED',
        actingUserId: userId,
        details: { sessionId, eventId, registrationId },
      });
      throw new BadRequestException('Rate limit exceeded. Please try again later.');
    }

    // Verify user exists
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
      select: { id: true, email: true },
    });

    if (!user) {
      throw new BadRequestException('User not found');
    }

    // Generate cryptographically secure token ID (jti)
    const jti = randomBytes(32).toString('hex');

    // Calculate expiry: session end time + 30 minutes, but not more than 24 hours from now
    const maxExpiry = new Date(Date.now() + 24 * 60 * 60 * 1000);
    const sessionEndWithBuffer = new Date(sessionEndTime.getTime() + this.MAX_EXPIRY_OFFSET);
    const expiresAt = sessionEndWithBuffer < maxExpiry ? sessionEndWithBuffer : maxExpiry;
    const ttlSeconds = Math.floor((expiresAt.getTime() - Date.now()) / 1000);

    // Create JWT payload
    const payload: Omit<MagicLinkPayload, 'iat' | 'exp'> = {
      sub: userId,
      jti,
      sessionId,
      eventId,
      registrationId,
      purpose: 'SESSION_JOIN',
    };

    // Sign the token
    const token = await this.jwtService.signAsync(payload, {
      secret: this.configService.get<string>('JWT_SECRET'),
      expiresIn: ttlSeconds,
    });

    // Store token metadata in Redis with TTL
    const redisKey = `magic-link:${jti}`;
    const tokenData = JSON.stringify({
      used: false,
      userId,
      registrationId,
      sessionId,
      eventId,
      createdAt: Date.now(),
    });
    await this.redis.setex(redisKey, ttlSeconds, tokenData);

    // Also track by registration for bulk revocation
    const regKey = `magic-link:reg:${registrationId}`;
    await this.redis.sadd(regKey, jti);
    await this.redis.expire(regKey, ttlSeconds);

    // Build the magic link URL
    const frontendUrl = (this.configService.get('FRONTEND_URL') || '').split(',')[0].trim();
    const url = `${frontendUrl}/auth/magic-link?token=${token}`;

    // Audit log
    await this.auditService.log({
      action: 'MAGIC_LINK_GENERATED',
      actingUserId: userId,
      details: {
        jti,
        sessionId,
        eventId,
        registrationId,
        expiresAt: expiresAt.toISOString(),
      },
    });

    this.logger.log(`Magic link generated for user ${userId}, session ${sessionId}`);

    return { token, url, expiresAt };
  }

  /**
   * Validate magic link token and return auth credentials
   */
  async validateAndAuthenticate(token: string): Promise<MagicLinkValidationResult> {
    let payload: MagicLinkPayload;

    // Verify JWT signature and expiry
    try {
      payload = await this.jwtService.verifyAsync<MagicLinkPayload>(token, {
        secret: this.configService.get<string>('JWT_SECRET'),
      });
    } catch (error) {
      this.logger.warn(`Invalid magic link token: ${error.message}`);
      return { valid: false, error: 'TOKEN_INVALID' };
    }

    // Validate purpose
    if (payload.purpose !== 'SESSION_JOIN') {
      this.logger.warn(`Invalid magic link purpose: ${payload.purpose}`);
      return { valid: false, error: 'TOKEN_INVALID' };
    }

    // Check if token exists in Redis and hasn't been used/revoked
    const redisKey = `magic-link:${payload.jti}`;
    const tokenDataStr = await this.redis.get(redisKey);

    if (!tokenDataStr) {
      // Token not found - could be expired, revoked, or never existed
      this.logger.warn(`Magic link token not found in Redis: ${payload.jti}`);
      return { valid: false, error: 'TOKEN_EXPIRED' };
    }

    const tokenData = JSON.parse(tokenDataStr);

    // Check if already used
    if (tokenData.used) {
      this.logger.warn(`Magic link token already used: ${payload.jti}`);
      await this.auditService.log({
        action: 'MAGIC_LINK_REUSE_ATTEMPT',
        actingUserId: payload.sub,
        details: { jti: payload.jti, sessionId: payload.sessionId },
      });
      return { valid: false, error: 'TOKEN_USED' };
    }

    // Fetch user
    const user = await this.prisma.user.findUnique({
      where: { id: payload.sub },
      select: {
        id: true,
        email: true,
        first_name: true,
        last_name: true,
        tier: true,
        preferredLanguage: true,
        sponsorId: true,
        isTwoFactorEnabled: true,
        userType: true,
      },
    });

    if (!user) {
      this.logger.warn(`User not found for magic link: ${payload.sub}`);
      return { valid: false, error: 'USER_NOT_FOUND' };
    }

    // Mark token as used (atomically)
    tokenData.used = true;
    tokenData.usedAt = Date.now();
    const ttl = await this.redis.ttl(redisKey);
    if (ttl > 0) {
      await this.redis.setex(redisKey, ttl, JSON.stringify(tokenData));
    }

    // Generate access and refresh tokens for the user
    const refreshTokenId = randomBytes(32).toString('hex');

    // Attendee-style JWT (no orgId required for session joining)
    const accessTokenPayload = {
      sub: user.id,
      email: user.email,
      permissions: ['session:join'],
      tier: (user.tier as 'default' | 'vip') || 'default',
      preferredLanguage: user.preferredLanguage || 'en',
      sponsorId: user.sponsorId || undefined,
      is2FAEnabled: user.isTwoFactorEnabled,
      // Include session context for the redirect
      magicLinkSessionId: payload.sessionId,
      magicLinkEventId: payload.eventId,
    };

    const refreshTokenPayload = {
      sub: user.id,
      jti: refreshTokenId,
    };

    const [accessToken, refreshToken] = await Promise.all([
      this.jwtService.signAsync(accessTokenPayload, {
        secret: this.configService.get<string>('JWT_SECRET'),
        expiresIn: '1d',
      }),
      this.jwtService.signAsync(refreshTokenPayload, {
        secret: this.configService.get<string>('JWT_REFRESH_SECRET'),
        expiresIn: '7d',
      }),
    ]);

    // Audit log successful authentication
    await this.auditService.log({
      action: 'MAGIC_LINK_AUTH_SUCCESS',
      actingUserId: user.id,
      details: {
        jti: payload.jti,
        sessionId: payload.sessionId,
        eventId: payload.eventId,
        registrationId: payload.registrationId,
      },
    });

    this.logger.log(`Magic link authentication successful for user ${user.id}`);

    // Build redirect URL
    const frontendUrl = (this.configService.get('FRONTEND_URL') || '').split(',')[0].trim();
    const redirectUrl = `${frontendUrl}/events/${payload.eventId}/sessions/${payload.sessionId}`;

    return {
      valid: true,
      accessToken,
      refreshToken,
      user: {
        id: user.id,
        email: user.email,
        firstName: user.first_name || '',
        lastName: user.last_name || '',
      },
      redirect: {
        sessionId: payload.sessionId,
        eventId: payload.eventId,
        url: redirectUrl,
      },
    };
  }

  /**
   * Revoke a specific magic link token by jti
   */
  async revoke(jti: string): Promise<void> {
    const redisKey = `magic-link:${jti}`;
    const tokenDataStr = await this.redis.get(redisKey);

    if (tokenDataStr) {
      const tokenData = JSON.parse(tokenDataStr);

      // Delete the token from Redis
      await this.redis.del(redisKey);

      // Remove from registration set if exists
      if (tokenData.registrationId) {
        const regKey = `magic-link:reg:${tokenData.registrationId}`;
        await this.redis.srem(regKey, jti);
      }

      await this.auditService.log({
        action: 'MAGIC_LINK_REVOKED',
        actingUserId: tokenData.userId,
        details: { jti, registrationId: tokenData.registrationId },
      });

      this.logger.log(`Magic link token revoked: ${jti}`);
    }
  }

  /**
   * Revoke all magic link tokens for a registration (e.g., when registration is cancelled)
   */
  async revokeAllForRegistration(registrationId: string): Promise<void> {
    const regKey = `magic-link:reg:${registrationId}`;
    const jtis = await this.redis.smembers(regKey);

    if (jtis.length > 0) {
      // Delete all token keys
      const tokenKeys = jtis.map(jti => `magic-link:${jti}`);
      await this.redis.del(...tokenKeys);

      // Delete the registration set
      await this.redis.del(regKey);

      await this.auditService.log({
        action: 'MAGIC_LINK_BULK_REVOKED',
        actingUserId: 'system',
        details: { registrationId, count: jtis.length },
      });

      this.logger.log(`Revoked ${jtis.length} magic link tokens for registration ${registrationId}`);
    }
  }

  /**
   * Check if a token is still valid (without consuming it)
   */
  async checkTokenStatus(jti: string): Promise<{ valid: boolean; used: boolean; expiresIn: number }> {
    const redisKey = `magic-link:${jti}`;
    const [tokenDataStr, ttl] = await Promise.all([
      this.redis.get(redisKey),
      this.redis.ttl(redisKey),
    ]);

    if (!tokenDataStr || ttl < 0) {
      return { valid: false, used: false, expiresIn: 0 };
    }

    const tokenData = JSON.parse(tokenDataStr);
    return {
      valid: !tokenData.used,
      used: tokenData.used,
      expiresIn: ttl,
    };
  }
}
