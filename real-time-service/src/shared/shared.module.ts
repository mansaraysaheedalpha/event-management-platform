//src/shared/shared.module.ts
import { Module, Global } from '@nestjs/common';
import { Redis } from 'ioredis';
import { IdempotencyService } from './services/idempotency.service';
import { SubscriberService } from './services/subscriber.service';
import { HttpModule } from '@nestjs/axios';
import { PublisherService } from './services/publisher.service';
import { REDIS_CLIENT, REDIS_SUBSCRIBER_CLIENT } from './redis.constants';
import { EventEmitterModule } from '@nestjs/event-emitter';

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

// We define the providers here to be reused
const redisClientProvider = {
  provide: REDIS_CLIENT,
  useFactory: () => new Redis({ host: 'localhost', port: 6379 }),
};

const redisSubscriberProvider = {
  provide: REDIS_SUBSCRIBER_CLIENT,
  useFactory: () => new Redis({ host: 'localhost', port: 6379 }),
};
@Global()
@Module({
  imports: [
    HttpModule.register({
      // Register HttpModule to make it available for internal API calls
      timeout: 5000, // 5 second timeout for internal requests
    }),
    EventEmitterModule.forRoot(),
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
    // The missing provider for the subscriber client
    {
      provide: REDIS_SUBSCRIBER_CLIENT,
      useFactory: () => new Redis({ host: 'localhost', port: 6379 }),
    },
    redisClientProvider,
    redisSubscriberProvider,
    IdempotencyService,
    SubscriberService, // Provides subscriber-related functionalities
    PublisherService, // Provides event publishing functionalities
  ],
  exports: [
    IdempotencyService,
    HttpModule,
    PublisherService,
    redisClientProvider,
    redisSubscriberProvider,
  ],
})
export class SharedModule {}
