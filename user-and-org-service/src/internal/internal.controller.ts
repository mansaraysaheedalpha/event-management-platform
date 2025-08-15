//src/internal/internal.controller.ts
import { Controller, Get, Param, UseGuards } from '@nestjs/common';
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
}
