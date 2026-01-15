//src/networking/linkedin/linkedin.service.ts
import { Injectable, Logger, UnauthorizedException, BadRequestException, ServiceUnavailableException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from 'src/prisma.service';
import { encrypt, decrypt, isEncrypted } from 'src/common/utils/crypto.utils';
import { getLinkedInBreaker, CircuitBreakerOpenError } from 'src/common/utils/circuit-breaker';

export interface LinkedInProfile {
  id: string;
  firstName: string;
  lastName: string;
  profileUrl: string;
  headline?: string;
  pictureUrl?: string;
  email?: string;
}

export interface LinkedInTokens {
  accessToken: string;
  refreshToken?: string;
  expiresIn: number;
}

export interface LinkedInConnectionSuggestion {
  userId: string;
  linkedInId: string;
  linkedInUrl: string;
  name: string;
  headline?: string;
  suggestedMessage: string;
}

@Injectable()
export class LinkedInService {
  private readonly logger = new Logger(LinkedInService.name);
  private readonly clientId: string;
  private readonly clientSecret: string;
  private readonly redirectUri: string;
  private readonly encryptionKey: string;
  private readonly scopes = ['openid', 'profile', 'email', 'w_member_social'];

  constructor(
    private readonly prisma: PrismaService,
    private readonly configService: ConfigService,
  ) {
    this.clientId = this.configService.get<string>('LINKEDIN_CLIENT_ID') || '';
    this.clientSecret = this.configService.get<string>('LINKEDIN_CLIENT_SECRET') || '';
    this.redirectUri = this.configService.get<string>('LINKEDIN_REDIRECT_URI') || 'http://localhost:3000/api/auth/linkedin/callback';
    // Use JWT_SECRET as encryption key for LinkedIn tokens (or dedicated key)
    this.encryptionKey = this.configService.get<string>('LINKEDIN_ENCRYPTION_KEY')
      || this.configService.get<string>('JWT_SECRET')
      || '';

    if (!this.encryptionKey) {
      this.logger.warn('No encryption key configured - LinkedIn tokens will be stored unencrypted');
    }
  }

  /**
   * Encrypt a token value if encryption key is available.
   */
  private encryptToken(token: string): string {
    if (!this.encryptionKey || !token) return token;
    try {
      return encrypt(token, this.encryptionKey);
    } catch (error) {
      this.logger.error('Failed to encrypt token', error);
      return token; // Fall back to unencrypted
    }
  }

  /**
   * Decrypt a token value if it appears to be encrypted.
   */
  private decryptToken(encryptedToken: string): string {
    if (!this.encryptionKey || !encryptedToken) return encryptedToken;
    if (!isEncrypted(encryptedToken)) return encryptedToken; // Already plain text
    try {
      return decrypt(encryptedToken, this.encryptionKey);
    } catch (error) {
      this.logger.error('Failed to decrypt token', error);
      return encryptedToken; // Return as-is if decryption fails
    }
  }

  /**
   * Generate the LinkedIn OAuth authorization URL.
   */
  getAuthorizationUrl(state: string): string {
    const params = new URLSearchParams({
      response_type: 'code',
      client_id: this.clientId,
      redirect_uri: this.redirectUri,
      state,
      scope: this.scopes.join(' '),
    });

    return `https://www.linkedin.com/oauth/v2/authorization?${params.toString()}`;
  }

  /**
   * Exchange authorization code for access token.
   * Protected by circuit breaker to prevent cascade failures.
   */
  async exchangeCodeForToken(code: string): Promise<LinkedInTokens> {
    const breaker = getLinkedInBreaker();

    try {
      return await breaker.execute(async () => {
        const params = new URLSearchParams({
          grant_type: 'authorization_code',
          code,
          client_id: this.clientId,
          client_secret: this.clientSecret,
          redirect_uri: this.redirectUri,
        });

        const response = await fetch('https://www.linkedin.com/oauth/v2/accessToken', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: params.toString(),
        });

        if (!response.ok) {
          const error = await response.text();
          this.logger.error('LinkedIn token exchange failed', error);
          throw new UnauthorizedException('Failed to exchange LinkedIn authorization code');
        }

        const data = await response.json();
        return {
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          expiresIn: data.expires_in,
        };
      });
    } catch (error) {
      if (error instanceof CircuitBreakerOpenError) {
        this.logger.warn('LinkedIn API circuit breaker is open');
        throw new ServiceUnavailableException('LinkedIn service is temporarily unavailable. Please try again later.');
      }
      throw error;
    }
  }

  /**
   * Fetch LinkedIn profile using access token.
   * Protected by circuit breaker to prevent cascade failures.
   */
  async fetchProfile(accessToken: string): Promise<LinkedInProfile> {
    const breaker = getLinkedInBreaker();

    try {
      return await breaker.execute(async () => {
        // Fetch basic profile using OpenID Connect userinfo endpoint
        const profileResponse = await fetch('https://api.linkedin.com/v2/userinfo', {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        });

        if (!profileResponse.ok) {
          const error = await profileResponse.text();
          this.logger.error('LinkedIn profile fetch failed', error);
          throw new BadRequestException('Failed to fetch LinkedIn profile');
        }

        const profile = await profileResponse.json();

        return {
          id: profile.sub,
          firstName: profile.given_name || '',
          lastName: profile.family_name || '',
          profileUrl: `https://www.linkedin.com/in/${profile.sub}`,
          headline: profile.headline,
          pictureUrl: profile.picture,
          email: profile.email,
        };
      });
    } catch (error) {
      if (error instanceof CircuitBreakerOpenError) {
        this.logger.warn('LinkedIn API circuit breaker is open');
        throw new ServiceUnavailableException('LinkedIn service is temporarily unavailable. Please try again later.');
      }
      throw error;
    }
  }

  /**
   * Connect a user's account with LinkedIn.
   */
  async connectLinkedIn(userId: string, code: string): Promise<LinkedInProfile> {
    // Exchange code for tokens
    const tokens = await this.exchangeCodeForToken(code);

    // Fetch profile
    const profile = await this.fetchProfile(tokens.accessToken);

    // Calculate token expiry
    const expiresAt = new Date(Date.now() + tokens.expiresIn * 1000);

    // Encrypt tokens before storing
    const encryptedAccessToken = this.encryptToken(tokens.accessToken);
    const encryptedRefreshToken = tokens.refreshToken
      ? this.encryptToken(tokens.refreshToken)
      : null;

    // Update user with LinkedIn data
    await this.prisma.userReference.update({
      where: { id: userId },
      data: {
        linkedInId: profile.id,
        linkedInUrl: profile.profileUrl,
        linkedInHeadline: profile.headline,
        linkedInAccessToken: encryptedAccessToken,
        linkedInRefreshToken: encryptedRefreshToken,
        linkedInTokenExpiresAt: expiresAt,
        // Optionally update avatar if user doesn't have one
        avatarUrl: profile.pictureUrl,
      },
    });

    this.logger.log(`LinkedIn connected for user ${userId}`);
    return profile;
  }

  /**
   * Disconnect LinkedIn from a user's account.
   */
  async disconnectLinkedIn(userId: string): Promise<void> {
    await this.prisma.userReference.update({
      where: { id: userId },
      data: {
        linkedInId: null,
        linkedInUrl: null,
        linkedInHeadline: null,
        linkedInAccessToken: null,
        linkedInRefreshToken: null,
        linkedInTokenExpiresAt: null,
      },
    });

    this.logger.log(`LinkedIn disconnected for user ${userId}`);
  }

  /**
   * Check if a user has LinkedIn connected.
   */
  async isLinkedInConnected(userId: string): Promise<boolean> {
    const user = await this.prisma.userReference.findUnique({
      where: { id: userId },
      select: { linkedInId: true, linkedInAccessToken: true },
    });

    return !!(user?.linkedInId && user?.linkedInAccessToken);
  }

  /**
   * Get LinkedIn profile URL for a user.
   */
  async getLinkedInUrl(userId: string): Promise<string | null> {
    const user = await this.prisma.userReference.findUnique({
      where: { id: userId },
      select: { linkedInUrl: true },
    });

    return user?.linkedInUrl || null;
  }

  /**
   * Generate a suggested connection message for LinkedIn.
   */
  generateConnectionMessage(
    userName: string,
    eventName: string,
    sharedContext?: string,
  ): string {
    if (sharedContext) {
      return `Hi ${userName}! We met at ${eventName} and I noticed we both ${sharedContext}. Would love to connect here on LinkedIn to stay in touch!`;
    }

    return `Hi ${userName}! It was great meeting you at ${eventName}. Would love to connect here on LinkedIn to continue our conversation!`;
  }

  /**
   * Get LinkedIn connection suggestions for a user's event connections.
   */
  async getLinkedInSuggestions(
    userId: string,
    eventId: string,
  ): Promise<LinkedInConnectionSuggestion[]> {
    // Get user's connections at this event who have LinkedIn
    const connections = await this.prisma.connection.findMany({
      where: {
        eventId,
        OR: [{ userAId: userId }, { userBId: userId }],
      },
      include: {
        userA: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            linkedInId: true,
            linkedInUrl: true,
            linkedInHeadline: true,
          },
        },
        userB: {
          select: {
            id: true,
            firstName: true,
            lastName: true,
            linkedInId: true,
            linkedInUrl: true,
            linkedInHeadline: true,
          },
        },
        contexts: true,
      },
    });

    const suggestions: LinkedInConnectionSuggestion[] = [];

    for (const conn of connections) {
      const otherUser = conn.userAId === userId ? conn.userB : conn.userA;

      // Skip if other user doesn't have LinkedIn
      if (!otherUser.linkedInId || !otherUser.linkedInUrl) continue;

      const name = [otherUser.firstName, otherUser.lastName].filter(Boolean).join(' ') || 'Connection';
      const sharedContext = conn.contexts[0]?.contextValue;

      suggestions.push({
        userId: otherUser.id,
        linkedInId: otherUser.linkedInId,
        linkedInUrl: otherUser.linkedInUrl,
        name,
        headline: otherUser.linkedInHeadline || undefined,
        suggestedMessage: this.generateConnectionMessage(
          name.split(' ')[0],
          'the event',
          sharedContext,
        ),
      });
    }

    return suggestions;
  }

  /**
   * Refresh access token if expired.
   */
  async refreshTokenIfNeeded(userId: string): Promise<string | null> {
    const user = await this.prisma.userReference.findUnique({
      where: { id: userId },
      select: {
        linkedInAccessToken: true,
        linkedInRefreshToken: true,
        linkedInTokenExpiresAt: true,
      },
    });

    if (!user?.linkedInAccessToken) return null;

    // Decrypt the stored access token
    const decryptedAccessToken = this.decryptToken(user.linkedInAccessToken);

    // Check if token is still valid (with 5 min buffer)
    if (user.linkedInTokenExpiresAt && user.linkedInTokenExpiresAt > new Date(Date.now() + 5 * 60 * 1000)) {
      return decryptedAccessToken;
    }

    // Token expired, try to refresh
    if (!user.linkedInRefreshToken) {
      this.logger.warn(`LinkedIn token expired for user ${userId} and no refresh token available`);
      return null;
    }

    // Decrypt refresh token for API call
    const decryptedRefreshToken = this.decryptToken(user.linkedInRefreshToken);

    const breaker = getLinkedInBreaker();

    try {
      const data = await breaker.execute(async () => {
        const params = new URLSearchParams({
          grant_type: 'refresh_token',
          refresh_token: decryptedRefreshToken,
          client_id: this.clientId,
          client_secret: this.clientSecret,
        });

        const response = await fetch('https://www.linkedin.com/oauth/v2/accessToken', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: params.toString(),
        });

        if (!response.ok) {
          throw new Error('LinkedIn token refresh failed');
        }

        return await response.json();
      });

      const expiresAt = new Date(Date.now() + data.expires_in * 1000);

      // Encrypt new tokens before storing
      const encryptedNewAccessToken = this.encryptToken(data.access_token);
      const encryptedNewRefreshToken = data.refresh_token
        ? this.encryptToken(data.refresh_token)
        : user.linkedInRefreshToken; // Keep existing encrypted refresh token

      await this.prisma.userReference.update({
        where: { id: userId },
        data: {
          linkedInAccessToken: encryptedNewAccessToken,
          linkedInRefreshToken: encryptedNewRefreshToken,
          linkedInTokenExpiresAt: expiresAt,
        },
      });

      return data.access_token;
    } catch (error) {
      if (error instanceof CircuitBreakerOpenError) {
        this.logger.warn('LinkedIn API circuit breaker is open during token refresh');
        return null;
      }
      this.logger.error('LinkedIn token refresh error', error);
      return null;
    }
  }
}
