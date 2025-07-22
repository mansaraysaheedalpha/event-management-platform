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
    // This configuration should ideally come from a ConfigService
    return new Redis({
      host: 'localhost', // The name of our docker service is 'redis' but we connect via localhost
      port: 6379,
    });
  },
};

@Global() // Makes the providers available everywhere without importing SharedModule
@Module({
  providers: [redisProvider, IdempotencyService],
  exports: [IdempotencyService], // Export the service for injection
})
export class SharedModule {}
