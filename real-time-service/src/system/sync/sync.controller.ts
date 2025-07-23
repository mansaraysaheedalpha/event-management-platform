import { Controller, Get, Query, UseGuards, Req } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { SyncService } from './sync.service';

/**
 * The `SyncController` handles data synchronization between the client
 * and server by exposing a protected endpoint that returns user-specific
 * changes since a given timestamp.
 *
 * This is commonly used for offline-capable apps or real-time sync workflows.
 *
 * @example
 * // Client hits endpoint with last sync timestamp
 * GET /sync/changes?since=2024-07-13T10:00:00Z
 * Authorization: Bearer <jwt_token>
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
    @Query('since') since: string,
  ) {
    const userId = req.user.sub;
    return this.syncService.getChangesSince(userId, since);
  }
}
