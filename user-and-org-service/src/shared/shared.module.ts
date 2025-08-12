import { Module, Global } from '@nestjs/common';
import { Redis } from 'ioredis';
import {
  IdempotencyService,
  REDIS_CLIENT,
} from './services/idempotency.service';

// This provider creates the Redis client instance.
const redisProvider = {
  provide: REDIS_CLIENT,
  useFactory: () => {
    const isProd = process.env.NODE_ENV === 'production';
    return new Redis({
      host: isProd ? process.env.REDIS_HOST : 'localhost',
      port: isProd ? Number(process.env.REDIS_PORT) : 6379,
    });
  },
};

@Global() // Makes the providers available everywhere without importing SharedModule
@Module({
  providers: [redisProvider, IdempotencyService],
  exports: [IdempotencyService, REDIS_CLIENT], // Export the service for injection
})
export class SharedModule {}
