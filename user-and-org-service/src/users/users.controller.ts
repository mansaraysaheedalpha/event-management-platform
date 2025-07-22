// src/users/users.controller.ts
import {
  Controller,
  Post,
  Body,
  Get,
  UseGuards,
  Request,
  Req,
  Patch,
  Put,
  Param,
} from '@nestjs/common';
import { RegisterUserDto } from './dto/register-user.dto';
import { UsersService } from './users.service';
import { AuthGuard } from '@nestjs/passport';
import { Throttle } from '@nestjs/throttler';
import { UpdateProfileDTO } from './dto/update-profile.dto';
import { ChangePasswordDTO } from './dto/change-password.dto';
import { RequestEmailChangeDto } from './dto/request-email-change.dto';

@Controller('users')
export class UsersController {
  constructor(private usersService: UsersService) {}

  @Throttle({ default: { limit: 5, ttl: 60000 } })
  @Post()
  async register(@Body() registerUserDto: RegisterUserDto) {
    return await this.usersService.create(registerUserDto);
  }

  @Get('me')
  @UseGuards(AuthGuard('jwt'))
  async getMyProfile(@Request() req: { user: { sub: string } }) {
    const userId = req.user.sub;
    return this.usersService.findOne(userId);
  }

  @Patch('me')
  @UseGuards(AuthGuard('jwt'))
  async updateUserProfile(
    @Body() updateProfileDto: UpdateProfileDTO,
    @Req() req: { user: { sub: string } },
  ) {
    const userId = req.user.sub;
    return await this.usersService.updateProfile(userId, updateProfileDto);
  }

  @Put('me/password')
  @UseGuards(AuthGuard('jwt'))
  async ChangeUserPassword(
    @Body() changePasswordDto: ChangePasswordDTO,
    @Req() req: { user: { sub: string } },
  ) {
    const userId = req.user.sub;
    return await this.usersService.changePassword(
      userId,
      changePasswordDto.currentPassword,
      changePasswordDto.newPassword,
    );
  }

  // Endpoint for Step 1
  @Patch('me/email')
  @UseGuards(AuthGuard('jwt'))
  requestEmailChange(
    @Req() req: { user: { sub: string } },
    @Body() body: { newEmail: string },
  ) {
    return this.usersService.requestEmailChange(req.user.sub, body.newEmail);
  }

  // Endpoint for Step 2
  @Get('email-change/verify-old/:token')
  confirmOldEmail(@Param('token') token: string) {
    return this.usersService.confirmOldEmail(token);
  }

  // Endpoint for Step 3
  @Get('email-change/finalize/:token')
  finalizeEmailChange(@Param('token') token: string) {
    return this.usersService.finalizeEmailChange(token);
  }
}
