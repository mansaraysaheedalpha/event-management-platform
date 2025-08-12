//src/system/sync/sync.controller.ts
import { IsISO8601 } from 'class-validator';
/**
 * DTO for validating the 'since' query parameter as ISO8601 string.
 */
export class SyncChangesQueryDto {
  @IsISO8601()
  since: string;
}
import { Controller, Get, Query, UseGuards, Req } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { SyncService } from './sync.service';
import { SyncLogDto } from './dto/sync-log.dto';

/**
 * The `SyncController` handles data synchronization between the client
 * and server by exposing a protected endpoint that returns user-specific
 * changes since a given timestamp.
 *
 * This is commonly used for offline-capable apps or real-time sync workflows.
 *
 * @example
 * // Client hits endpoint with last sync timestamp
 * curl -X GET "http://localhost:3000/sync/changes?since=2024-07-13T10:00:00Z" \
 *   -H "Authorization: Bearer <jwt_token>"
 *
 * Typical HTTP response codes:
 *   200 - Success, returns array of changes
 *   401 - Unauthorized (missing or invalid token)
 *   400 - Bad Request (invalid 'since' parameter)
 */
@Controller('sync')
@UseGuards(AuthGuard('jwt')) // Protect this endpoint
export class SyncController {
  constructor(private readonly syncService: SyncService) {}

  /**
   * Returns all data changes for the authenticated user since the given timestamp.
   *
   * @param req - Request object containing the authenticated user's JWT payload
   * @param since - ISO timestamp string indicating when the last sync occurred
   * @returns Promise with changes since the given timestamp
   */
  @Get('changes')
  async getChanges(
    @Req() req: { user: { sub: string } },
    @Query() query: SyncChangesQueryDto,
  ): Promise<SyncLogDto[]> {
    const userId = req.user.sub;
    return this.syncService.getChangesSince(userId, query.since);
  }
}
