import { Module, Global } from '@nestjs/common';
import { Redis } from 'ioredis';
import {
  IdempotencyService,
  REDIS_CLIENT,
} from './services/idempotency.service';
import { SubscriberService } from './services/subscriber.service';
import { HttpModule } from '@nestjs/axios';
import { PublisherService } from './services/publisher.service';

// Key for the general-purpose Redis client
export { REDIS_CLIENT };

// NEW: Key for the dedicated subscriber Redis client
export const REDIS_SUBSCRIBER_CLIENT = 'REDIS_SUBSCRIBER_CLIENT';

/**
 * SharedModule is a global, reusable NestJS module providing:
 * - Configured Redis clients for general and subscriber use.
 * - HTTP client module for internal API calls.
 * - Shared services like IdempotencyService, SubscriberService, and PublisherService.
 *
 * This module is marked as @Global, so its providers and exports
 * are available throughout the entire application without needing
 * to import it everywhere explicitly.
 *
 * Redis clients connect to localhost on the default port 6379.
 *
 * @remarks
 * - HttpModule is registered with a 5-second timeout for internal requests.
 * - This module facilitates consistent and centralized resource sharing.
 */
@Global()
@Module({
  imports: [
    HttpModule.register({
      // Register HttpModule to make it available for internal API calls
      timeout: 5000, // 5 second timeout for internal requests
    }),
  ],
  providers: [
    // Provider for the general-purpose Redis client
    {
      provide: REDIS_CLIENT,
      useFactory: () => {
        const host = process.env.REDIS_HOST || 'localhost';
        const port = process.env.REDIS_PORT
          ? parseInt(process.env.REDIS_PORT, 10)
          : 6379;
        return new Redis({ host, port });
      },
    },
    // Provider for the dedicated subscriber Redis client (uses .duplicate() for shared connection)
    {
      provide: REDIS_SUBSCRIBER_CLIENT,
      useFactory: (redisClient: Redis) => redisClient.duplicate(),
      inject: [REDIS_CLIENT],
    },
    IdempotencyService,
    SubscriberService, // Provides subscriber-related functionalities
    PublisherService, // Provides event publishing functionalities
  ],
  exports: [IdempotencyService, HttpModule, PublisherService],
})
export class SharedModule {}
