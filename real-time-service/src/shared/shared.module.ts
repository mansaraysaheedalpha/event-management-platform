//src/shared/shared.module.ts
import { Module, Global } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { Redis } from 'ioredis';
import { IdempotencyService } from './services/idempotency.service';
import { SubscriberService } from './services/subscriber.service';
import { HttpModule } from '@nestjs/axios';
import { PublisherService } from './services/publisher.service';
import { REDIS_CLIENT, REDIS_SUBSCRIBER_CLIENT } from './redis.constants';
import { EventEmitterModule } from '@nestjs/event-emitter';
import { KafkaConsumerService } from './services/kafka.consumer.service';

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
      timeout: 5000,
    }),
    EventEmitterModule.forRoot(),
    ConfigModule,
  ],
  providers: [
    {
      provide: REDIS_CLIENT,
      useFactory: (configService: ConfigService) => {
        const redisUrl = configService.getOrThrow<string>('REDIS_URL');
        return new Redis(redisUrl);
      },
      inject: [ConfigService],
    },
    {
      provide: REDIS_SUBSCRIBER_CLIENT,
      useFactory: (configService: ConfigService) => {
        const redisUrl = configService.getOrThrow<string>('REDIS_URL');
        return new Redis(redisUrl);
      },
      inject: [ConfigService],
    },
    // ---------------------
    IdempotencyService,
    SubscriberService,
    PublisherService,
    KafkaConsumerService,
  ],
  exports: [
    IdempotencyService,
    HttpModule,
    PublisherService,
    REDIS_CLIENT,
    REDIS_SUBSCRIBER_CLIENT,
  ],
})
export class SharedModule {}
