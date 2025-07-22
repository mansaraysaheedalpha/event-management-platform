import { Inject, Injectable, Logger } from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { REDIS_CLIENT } from 'src/shared/services/idempotency.service'; // We can reuse the Redis client
import { Redis } from 'ioredis';

@Injectable()
export class PermissionsService {
  private readonly logger = new Logger(PermissionsService.name);
  private readonly CACHE_TTL = 3600; // Cache permissions for 1 hour

  constructor(
    private readonly prisma: PrismaService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
  ) {}

  async getPermissionsForRole(roleId: string): Promise<string[]> {
    const cacheKey = `permissions:role:${roleId}`;

    // 1. Try to get permissions from cache first
    try {
      const cachedPermissions = await this.redis.get(cacheKey);
      if (cachedPermissions) {
        this.logger.log(`Cache hit for role ${roleId}`);
        return JSON.parse(cachedPermissions);
      }
    } catch (error) {
      this.logger.error('Could not connect to Redis for cache lookup', error);
    }

    this.logger.log(`Cache miss for role ${roleId}. Fetching from DB.`);

    // 2. If not in cache, query the database
    const roleWithPermissions = await this.prisma.role.findUnique({
      where: { id: roleId },
      include: {
        permissions: {
          select: { name: true }, // Select only the name of the permission
        },
      },
    });

    if (!roleWithPermissions) {
      return []; // Return empty array if role doesn't exist
    }

    const permissions = roleWithPermissions.permissions.map((p) => p.name);

    // 3. Store the result in the cache for future requests
    try {
      await this.redis.set(
        cacheKey,
        JSON.stringify(permissions),
        'EX',
        this.CACHE_TTL,
      );
    } catch (error) {
      this.logger.error('Could not connect to Redis to set cache', error);
    }

    return permissions;
  }

  // We would also add methods here to create roles, assign permissions, etc.
}
