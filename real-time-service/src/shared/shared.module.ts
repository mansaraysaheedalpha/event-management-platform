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

@Global()
@Module({
  imports: [
    HttpModule.register({
      // <-- Register HttpModule to make it available
      timeout: 5000, // 5 second timeout for internal requests
    }),
  ],
  providers: [
    // Provider for the general-purpose client
    {
      provide: REDIS_CLIENT,
      useFactory: () => new Redis({ host: 'localhost', port: 6379 }),
    },
    // Provider for the subscriber client
    {
      provide: REDIS_SUBSCRIBER_CLIENT,
      useFactory: () => new Redis({ host: 'localhost', port: 6379 }),
    },
    IdempotencyService,
    SubscriberService, // Provide our new service
    PublisherService,
  ],
  exports: [IdempotencyService, HttpModule, PublisherService],
})
export class SharedModule {}
