import { Controller, Get, Query, UseGuards, Req } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { SyncService } from './sync.service';

@Controller('sync')
@UseGuards(AuthGuard('jwt')) // Protect this endpoint
export class SyncController {
  constructor(private readonly syncService: SyncService) {}

  @Get('changes')
  async getChanges(
    @Req() req: { user: { sub: string } },
    @Query('since') since: string, // Expect a query param like ?since=2024-07-13T10:00:00Z
  ) {
    const userId = req.user.sub;
    return this.syncService.getChangesSince(userId, since);
  }
}
