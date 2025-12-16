//src/common/guards/ws-throttler.guard.ts
import { ExecutionContext, Injectable } from '@nestjs/common';
import { ThrottlerGuard } from '@nestjs/throttler';
import { AuthenticatedSocket } from '../interfaces/auth.interface';
import { getAuthenticatedUser } from '../utils/auth.utils';

@Injectable()
export class WsThrottlerGuard extends ThrottlerGuard {
  /**
   * ✅ NEW METHOD ✅
   * This is the main entry point for the guard. We override it to add our custom logic.
   */
  async canActivate(context: ExecutionContext): Promise<boolean> {
    // Skip throttling for HTTP requests - this guard is designed for WebSockets only.
    // HTTP requests don't have WebSocket user data attached.
    if (context.getType() === 'http') {
      return true;
    }

    const data = context.switchToWs().getData();

    // If the event is an internal 'ping', bypass the throttler entirely.
    // The `data` check is a safety measure for unexpected message formats.
    if (data && data[0] === 'ping') {
      return true;
    }

    // For all other events, proceed with the original throttler logic,
    // which will use our custom `getLimit`, `getTTL`, etc., methods below.
    return super.canActivate(context);
  }

  /**
   * Overrides getTracker to use the authenticated user's ID from our custom socket.
   */
  protected async getTracker(req: AuthenticatedSocket): Promise<string> {
    return getAuthenticatedUser(req).sub;
  }

  /**
   * Overrides getLimit to dynamically return the limit based on the user's tier.
   */
  protected async getLimit(context: ExecutionContext): Promise<number> {
    const client = context.switchToWs().getClient<AuthenticatedSocket>();
    const user = getAuthenticatedUser(client);
    const tier = user.tier || 'default';

    const tierConfig = this.throttlers.find((opt) => opt.name === tier);

    const limit = tierConfig?.limit || 100;
    if (typeof limit === 'function') {
      return await limit(context);
    }
    return limit;
  }

  /**
   * Overrides getTimeToLive to dynamically return the TTL based on the user's tier.
   */
  protected async getTimeToLive(context: ExecutionContext): Promise<number> {
    const client = context.switchToWs().getClient<AuthenticatedSocket>();
    const user = getAuthenticatedUser(client);
    const tier = user.tier || 'default';

    const tierConfig = this.throttlers.find((opt) => opt.name === tier);

    const ttl = tierConfig?.ttl || 60000;
    let ttlInMillis: number;

    if (typeof ttl === 'function') {
      ttlInMillis = await ttl(context);
    } else {
      ttlInMillis = ttl;
    }

    // The library expects the TTL in seconds.
    return ttlInMillis / 1000;
  }

  /**
   * Overrides this method to correctly handle WebSocket contexts.
   */
  protected getRequestResponse(context: ExecutionContext): {
    req: any;
    res: any;
  } {
    const client = context.switchToWs().getClient<AuthenticatedSocket>();
    return { req: client, res: {} };
  }
}
