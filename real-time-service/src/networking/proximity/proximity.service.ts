//src/networking/proximity/proximity.service.ts
import { Inject, Injectable, Logger } from '@nestjs/common';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { UpdateLocationDto } from './dto/update-location.dto';

@Injectable()
export class ProximityService {
  private readonly logger = new Logger(ProximityService.name);
  private readonly SEARCH_RADIUS_METERS = 100; // Search within a 100-meter radius
  private readonly LOCATION_TTL_SECONDS = 3600; // Location data expires after 1 hour

  constructor(@Inject(REDIS_CLIENT) private readonly redis: Redis) {}

  /**
   * Gets the event-scoped Redis GEO key for storing user locations.
   * Each event has its own isolated location data to prevent cross-event data leaks.
   */
  private getGeoKey(eventId: string): string {
    return `event:${eventId}:locations`;
  }

  /**
   * Adds or updates a user's location in the Redis GEO set for a specific event.
   * @param userId The ID of the user.
   * @param dto The DTO containing the user's latitude, longitude, and eventId.
   */
  async updateUserLocation(
    userId: string,
    dto: UpdateLocationDto,
  ): Promise<void> {
    if (!dto.eventId) {
      this.logger.warn(
        `No eventId provided for user ${userId} location update - skipping`,
      );
      return;
    }

    const geoKey = this.getGeoKey(dto.eventId);

    // GEOADD [key] [longitude] [latitude] [member]
    await this.redis.geoadd(geoKey, dto.longitude, dto.latitude, userId);

    // Set TTL for automatic cleanup of stale location data
    await this.redis.expire(geoKey, this.LOCATION_TTL_SECONDS);

    this.logger.log(
      `Updated location for user ${userId} in event ${dto.eventId}`,
    );
  }

  /**
   * Finds all users within a specified radius of a given user within the same event.
   * @param userId The ID of the user to search around.
   * @param eventId The event ID to scope the search to.
   * @returns A list of nearby user IDs from the same event.
   */
  async findNearbyUsers(userId: string, eventId: string): Promise<string[]> {
    if (!eventId) {
      this.logger.warn(
        `No eventId provided for findNearbyUsers - returning empty array`,
      );
      return [];
    }

    const geoKey = this.getGeoKey(eventId);

    // GEORADIUSBYMEMBER [key] [member] [radius] m
    const nearbyUsers = await this.redis.georadiusbymember(
      geoKey,
      userId,
      this.SEARCH_RADIUS_METERS,
      'm', // 'm' for meters
    );

    // The result includes the user themselves, so we filter them out.
    return (nearbyUsers as string[]).filter(
      (nearbyUserId: string) => nearbyUserId !== userId,
    );
  }

  /**
   * Removes a user's location from a specific event.
   * Called when user stops tracking or disconnects.
   */
  async removeUserLocation(userId: string, eventId: string): Promise<void> {
    if (!eventId) return;

    const geoKey = this.getGeoKey(eventId);
    await this.redis.zrem(geoKey, userId);
    this.logger.log(
      `Removed location for user ${userId} from event ${eventId}`,
    );
  }
}
