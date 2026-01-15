// src/common/guards/rest-throttler.guard.ts
import { ExecutionContext, Injectable } from '@nestjs/common';
import { ThrottlerGuard } from '@nestjs/throttler';
import { JwtPayload } from '../interfaces/auth.interface';

/**
 * REST API Throttler Guard
 *
 * Applies rate limiting to HTTP/REST endpoints based on user tier.
 * Uses the user ID as the tracker for authenticated requests,
 * or falls back to IP address for unauthenticated requests.
 *
 * Tier limits (configured in ThrottlerModule):
 * - default: 100 requests per 60 seconds
 * - vip: 500 requests per 60 seconds
 */
@Injectable()
export class RestThrottlerGuard extends ThrottlerGuard {
  /**
   * Only activate for HTTP requests.
   */
  async canActivate(context: ExecutionContext): Promise<boolean> {
    // Only handle HTTP requests
    if (context.getType() !== 'http') {
      return true;
    }

    return super.canActivate(context);
  }

  /**
   * Use user ID for authenticated requests, IP for others.
   */
  protected async getTracker(req: any): Promise<string> {
    const user: JwtPayload | undefined = req.user;

    if (user?.sub) {
      return `user:${user.sub}`;
    }

    // Fall back to IP address
    return (
      req.ip ||
      req.headers['x-forwarded-for'] ||
      req.connection?.remoteAddress ||
      'unknown'
    );
  }

  /**
   * Get rate limit based on user tier.
   */
  protected async getLimit(context: ExecutionContext): Promise<number> {
    const request = context.switchToHttp().getRequest();
    const user: JwtPayload | undefined = request.user;
    const tier = user?.tier || 'default';

    const tierConfig = this.throttlers.find((opt) => opt.name === tier);

    const limit = tierConfig?.limit || 100;
    if (typeof limit === 'function') {
      return await limit(context);
    }
    return limit;
  }

  /**
   * Get TTL based on user tier.
   */
  protected async getTimeToLive(context: ExecutionContext): Promise<number> {
    const request = context.switchToHttp().getRequest();
    const user: JwtPayload | undefined = request.user;
    const tier = user?.tier || 'default';

    const tierConfig = this.throttlers.find((opt) => opt.name === tier);

    const ttl = tierConfig?.ttl || 60000;
    let ttlInMillis: number;

    if (typeof ttl === 'function') {
      ttlInMillis = await ttl(context);
    } else {
      ttlInMillis = ttl;
    }

    // Library expects TTL in seconds
    return ttlInMillis / 1000;
  }
}
