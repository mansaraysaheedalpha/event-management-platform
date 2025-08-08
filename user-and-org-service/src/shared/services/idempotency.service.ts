//src/shared/services/idempotency.service.ts
import { Injectable, Inject } from '@nestjs/common';
import { Redis } from 'ioredis';

// A descriptive key for our Redis provider
export const REDIS_CLIENT = 'REDIS_CLIENT';

@Injectable()
export class IdempotencyService {
  // The time-to-live for an idempotency key, in seconds.
  // 60 seconds is a reasonable default to prevent immediate duplicates.
  private readonly KEY_TTL = 60;

  constructor(@Inject(REDIS_CLIENT) private readonly redis: Redis) {}

  /**
   * Checks for the existence of an idempotency key and sets it if it doesn't exist.
   * This operation is atomic, making it safe from race conditions.
   *
   * @param key The unique idempotency key from the client.
   * @returns `true` if the key was new and the operation can proceed.
   * `false` if the key already existed (duplicate request).
   */
  async checkAndSet(key: string): Promise<boolean> {
    // We use Redis's SET command with special options:
    // 'value' -> The value can be anything, we use '1'.
    // 'EX' -> Set an expiration time (in seconds).
    // 'NX' -> Only set the key if it does not already exist.
    // This command returns 'OK' if the key was set, or null if it already existed.
    const result = await this.redis.set(
      `idempotency:${key}`, // We prefix the key for better organization in Redis
      '1',
      'EX',
      this.KEY_TTL,
      'NX',
    );

    return result === 'OK';
  }
}
