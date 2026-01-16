//src/internal/internal.controller.ts
import { Controller, Get, Patch, Param, Body, UseGuards } from '@nestjs/common';
import { UsersService } from 'src/users/users.service';
import { InternalApiKeyGuard } from 'src/auth/guards/internal-api-key.guard';

@Controller('internal')
@UseGuards(InternalApiKeyGuard) // Protect all routes in this controller
export class InternalController {
  constructor(private readonly usersService: UsersService) {}

  @Get('users/:id')
  async getUserById(@Param('id') id: string) {
    return this.usersService.findUserForInternal(id);
  }

  /**
   * Link a user to a sponsor (called when accepting sponsor invitation).
   * Protected by InternalApiKeyGuard - requires x-internal-api-key header.
   */
  @Patch('users/:userId/sponsor')
  async linkUserToSponsor(
    @Param('userId') userId: string,
    @Body() body: { sponsorId: string },
  ) {
    return this.usersService.linkUserToSponsor(userId, body.sponsorId);
  }

  /**
   * Unlink a user from their sponsor (called when removing from sponsor team).
   * Protected by InternalApiKeyGuard - requires x-internal-api-key header.
   */
  @Patch('users/:userId/sponsor/unlink')
  async unlinkUserFromSponsor(@Param('userId') userId: string) {
    return this.usersService.unlinkUserFromSponsor(userId);
  }
}
