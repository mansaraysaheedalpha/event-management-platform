//src/internal/internal.controller.ts
import {
  Controller,
  Get,
  Post,
  Patch,
  Param,
  Body,
  Query,
  UseGuards,
  BadRequestException,
  UnauthorizedException,
} from '@nestjs/common';
import { IsEmail, IsString, MinLength, IsNotEmpty } from 'class-validator';
import * as bcrypt from 'bcrypt';
import { UsersService } from 'src/users/users.service';
import { AuthService } from 'src/auth/auth.service';
import { PrismaService } from 'src/prisma.service';
import { InternalApiKeyGuard } from 'src/auth/guards/internal-api-key.guard';

// DTOs for sponsor invitation handling
class CreateSponsorUserDto {
  @IsEmail()
  email: string;

  @IsString()
  @IsNotEmpty()
  first_name: string;

  @IsString()
  @IsNotEmpty()
  last_name: string;

  @IsString()
  @MinLength(8)
  password: string;

  @IsString()
  @IsNotEmpty()
  sponsorId: string;
}

class VerifySponsorUserDto {
  @IsEmail()
  email: string;

  @IsString()
  @IsNotEmpty()
  password: string;

  @IsString()
  @IsNotEmpty()
  sponsorId: string;
}

@Controller('internal')
@UseGuards(InternalApiKeyGuard) // Protect all routes in this controller
export class InternalController {
  constructor(
    private readonly usersService: UsersService,
    private readonly authService: AuthService,
    private readonly prisma: PrismaService,
  ) {}

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

  // ==================== Sponsor Invitation Endpoints ====================

  /**
   * Check if a user exists by email (for sponsor invitation preview).
   * Returns whether the user exists and their first name if so.
   */
  @Get('sponsor-invitations/check-email')
  async checkEmailExists(@Query('email') email: string) {
    if (!email) {
      throw new BadRequestException('Email is required');
    }

    const user = await this.prisma.user.findUnique({
      where: { email: email.toLowerCase() },
      select: { id: true, first_name: true },
    });

    return {
      userExists: !!user,
      existingUserFirstName: user?.first_name || null,
    };
  }

  /**
   * Create a new user for sponsor invitation acceptance.
   * Creates the user, links them to the sponsor, and returns auth tokens.
   */
  @Post('sponsor-invitations/create-user')
  async createSponsorUser(@Body() dto: CreateSponsorUserDto) {
    const { email, first_name, last_name, password, sponsorId } = dto;

    // Check if user already exists
    const existingUser = await this.prisma.user.findUnique({
      where: { email: email.toLowerCase() },
    });

    if (existingUser) {
      throw new BadRequestException(
        'An account already exists for this email. Please use the existing user flow.',
      );
    }

    // Password validation is handled by class-validator @MinLength(8) decorator

    // Create user with sponsor link (use ATTENDEE type for sponsor reps)
    const hashedPassword = await bcrypt.hash(password, 10);
    const newUser = await this.prisma.user.create({
      data: {
        email: email.toLowerCase(),
        first_name,
        last_name,
        password: hashedPassword,
        sponsorId,
        userType: 'ATTENDEE',
      },
      select: {
        id: true,
        email: true,
        first_name: true,
        last_name: true,
        imageUrl: true,
        tier: true,
        sponsorId: true,
        preferredLanguage: true,
        isTwoFactorEnabled: true,
        userType: true,
      },
    });

    // Generate tokens for sponsor representative (no org membership required)
    const tokens = await this.authService.getTokensForAttendee(newUser);

    return {
      user: {
        id: newUser.id,
        email: newUser.email,
        firstName: newUser.first_name,
        lastName: newUser.last_name,
      },
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
    };
  }

  /**
   * Verify an existing user for sponsor invitation acceptance.
   * Validates password, links them to the sponsor, and returns auth tokens.
   */
  @Post('sponsor-invitations/verify-user')
  async verifySponsorUser(@Body() dto: VerifySponsorUserDto) {
    const { email, password, sponsorId } = dto;

    // Find existing user
    const user = await this.prisma.user.findUnique({
      where: { email: email.toLowerCase() },
      select: {
        id: true,
        email: true,
        first_name: true,
        last_name: true,
        password: true,
        imageUrl: true,
        tier: true,
        sponsorId: true,
        preferredLanguage: true,
        isTwoFactorEnabled: true,
        userType: true,
      },
    });

    if (!user) {
      throw new BadRequestException(
        'No account exists for this email. Please use the new user registration flow.',
      );
    }

    // Verify password
    const passwordValid = await bcrypt.compare(password, user.password);
    if (!passwordValid) {
      throw new UnauthorizedException(
        'Invalid password. Please enter your existing account password.',
      );
    }

    // Update user with sponsor link (they might already have a sponsorId from another sponsor)
    const updatedUser = await this.prisma.user.update({
      where: { id: user.id },
      data: { sponsorId },
      select: {
        id: true,
        email: true,
        first_name: true,
        last_name: true,
        imageUrl: true,
        tier: true,
        sponsorId: true,
        preferredLanguage: true,
        isTwoFactorEnabled: true,
        userType: true,
      },
    });

    // Generate tokens for sponsor representative
    const tokens = await this.authService.getTokensForAttendee(updatedUser);

    return {
      user: {
        id: updatedUser.id,
        email: updatedUser.email,
        firstName: updatedUser.first_name,
        lastName: updatedUser.last_name,
      },
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
    };
  }
}
