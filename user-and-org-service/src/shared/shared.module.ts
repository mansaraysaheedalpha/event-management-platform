// src/shared/shared.module.ts

import { Module, Global } from '@nestjs/common';
import { Redis } from 'ioredis';
import { IdempotencyService } from './services/idempotency.service';
import { REDIS_CLIENT } from './redis.constants'; // Assuming you have this constants file
import { ConfigService } from '@nestjs/config';

const redisProvider = {
  provide: REDIS_CLIENT,
  // **FIX**: Inject ConfigService to safely get environment variables
  inject: [ConfigService],
  useFactory: (configService: ConfigService) => {
    const redisUrl = configService.get<string>('REDIS_URL');
    if (!redisUrl) {
      throw new Error('REDIS_URL is not configured in the environment.');
    }
    return new Redis(redisUrl);
  },
};

@Global()
@Module({
  providers: [redisProvider, IdempotencyService],
  exports: [IdempotencyService, REDIS_CLIENT],
})
export class SharedModule {}