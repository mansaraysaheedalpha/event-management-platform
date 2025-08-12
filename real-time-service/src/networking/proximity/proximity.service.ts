//src/networking/proximity/proximity.service.ts
import { Inject, Injectable, Logger } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { UpdateLocationDto } from './dto/update-location.dto';

@Injectable()
export class ProximityService {
  private readonly logger = new Logger(ProximityService.name);
  private readonly GEO_KEY = 'event:locations'; // A single key for all user locations in an event
  private readonly SEARCH_RADIUS_METERS = 100; // Search within a 100-meter radius

  constructor(@Inject(REDIS_CLIENT) private readonly redis: Redis) {}

  /**
   * Adds or updates a user's location in the Redis GEO set.
   * @param userId The ID of the user.
   * @param dto The DTO containing the user's latitude and longitude.
   */
  async updateUserLocation(
    userId: string,
    dto: UpdateLocationDto,
  ): Promise<void> {
    // GEOADD [key] [longitude] [latitude] [member]
    await this.redis.geoadd(this.GEO_KEY, dto.longitude, dto.latitude, userId);
    this.logger.log(`Updated location for user ${userId}`);
  }

  /**
   * Finds all users within a specified radius of a given user.
   * @param userId The ID of the user to search around.
   * @returns A list of nearby user IDs.
   */
  async findNearbyUsers(userId: string): Promise<string[]> {
    // GEORADIUSBYMEMBER [key] [member] [radius] m
    const nearbyUsers = await this.redis.georadiusbymember(
      this.GEO_KEY,
      userId,
      this.SEARCH_RADIUS_METERS,
      'm', // 'm' for meters
    );

    // The result includes the user themselves, so we filter them out.
    return (nearbyUsers as string[]).filter(
      (nearbyUserId: string) => nearbyUserId !== userId,
    );
  }
}
