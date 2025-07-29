import { ExecutionContext, Injectable } from '@nestjs/common';
import { ThrottlerGuard } from '@nestjs/throttler';
import { AuthenticatedSocket } from '../interfaces/auth.interface';
import { getAuthenticatedUser } from '../utils/auth.utils';

@Injectable()
export class WsThrottlerGuard extends ThrottlerGuard {
  /**
   * Overrides getTracker to use the authenticated user's ID from our custom socket.
   * FIX: The method must be async and return a Promise<string>.
   */
  protected async getTracker(req: AuthenticatedSocket): Promise<string> {
    return getAuthenticatedUser(req).sub;
  }

  /**
   * Overrides getLimit to dynamically return the limit based on the user's tier.
   * FIX: The method must be async and correctly access the named throttler configs.
   */
  protected async getLimit(context: ExecutionContext): Promise<number> {
    const client = context.switchToWs().getClient<AuthenticatedSocket>();
    const user = getAuthenticatedUser(client);
    const tier = user.tier || 'default';

    // FIX: The named configurations are stored in the `throttlers` property, not `options`.
    const tierConfig = this.throttlers.find((opt) => opt.name === tier);

    // FIX: Handle the case where limit can be a function or a number
    const limit = tierConfig?.limit || 100;
    if (typeof limit === 'function') {
      return await limit(context);
    }
    return limit;
  }

  /**
   * Overrides getTimeToLive to dynamically return the TTL based on the user's tier.
   * FIX: The method must be async and correctly access the named throttler configs.
   */
  protected async getTimeToLive(context: ExecutionContext): Promise<number> {
    const client = context.switchToWs().getClient<AuthenticatedSocket>();
    const user = getAuthenticatedUser(client);
    const tier = user.tier || 'default';

    const tierConfig = this.throttlers.find((opt) => opt.name === tier);

    // FIX: Handle the case where ttl can be a function or a number
    const ttl = tierConfig?.ttl || 60000;
    let ttlInMillis: number;

    if (typeof ttl === 'function') {
      ttlInMillis = await ttl(context);
    } else {
      ttlInMillis = ttl;
    }

    // FIX: The library expects the TTL in seconds.
    return ttlInMillis / 1000;
  }

  // Override this method to correctly handle WebSocket contexts
  protected getRequestResponse(context: ExecutionContext): {
    req: any;
    res: any;
  } {
    const client = context.switchToWs().getClient<AuthenticatedSocket>();
    // FIX: The `res` object doesn't exist on a WebSocket client, so we can use an empty object.
    return { req: client, res: {} };
  }
}
