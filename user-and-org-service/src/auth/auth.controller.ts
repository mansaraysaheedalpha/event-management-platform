//src/auth/.auth.controller.ts
import {
  Controller,
  Post,
  Get,
  Body,
  UseGuards,
  HttpCode,
  HttpStatus,
  Res,
  Req,
  Param,
  ForbiddenException,
} from '@nestjs/common';
import { Response } from 'express';
import { LoginDTO } from './dto/login.dto';
import { AuthService } from './auth.service';
import { AuthGuard } from '@nestjs/passport';
import { RefreshTokenGuard } from './guards/refresh-token.guard';
import { ConfigService } from '@nestjs/config';
import { InvitationsService } from 'src/invitations/invitations.service';
import { Login2faDto } from './dto/login-2fa.dto';
import { AcceptInvitationDTO } from 'src/invitations/dto/AcceptInvitationDTO';
import { AcceptInvitationExistingUserDTO } from 'src/invitations/dto/AcceptInvitationExistingUserDTO';
import { PasswordResetRequestDTO } from './dto/request-reset.dto';
import { PerformPasswordResetDTO } from './dto/perform-reset.dto';
import { SwitchOrganizationDTO } from './dto/switch-org.dto';

@Controller('auth')
export class AuthController {
  constructor(
    private readonly authService: AuthService,
    private readonly invitationService: InvitationsService,
    private readonly configService: ConfigService, // <-- Inject ConfigService
  ) {}

  @Post('login')
  @HttpCode(HttpStatus.OK)
  async login(
    @Body() loginDTO: LoginDTO,
    @Res({ passthrough: true }) res: Response,
  ) {
    const loginResult = await this.authService.login(loginDTO);

    // This now correctly handles both special cases
    if ('onboardingToken' in loginResult || 'userHasNoOrgs' in loginResult) {
      throw new ForbiddenException(
        'This user must complete onboarding. Please use the main GraphQL application.',
      );
    }

    if ('requires2FA' in loginResult) {
      return loginResult;
    }

    const { access_token, refresh_token } = loginResult;
    res.cookie('refresh_token', refresh_token, {
      httpOnly: true,
      secure: this.configService.get('NODE_ENV') !== 'development',
      sameSite: 'strict',
      maxAge: 7 * 24 * 60 * 60 * 1000,
    });

    return { access_token };
  }

  @Post('login/2fa')
  @HttpCode(HttpStatus.OK)
  async Login2FA(
    @Body() login2faDto: Login2faDto,
    @Res({ passthrough: true }) res: Response,
  ): Promise<{ access_token: string }> {
    const tokens = await this.authService.login2FA(
      login2faDto.userId,
      login2faDto.code,
    );
    res.cookie('refresh_token', tokens.refresh_token, {
      httpOnly: true,
      secure: this.configService.get('NODE_ENV') !== 'development',
      sameSite: 'strict',
      maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
    });
    return { access_token: tokens.access_token };
  }

  @Post('logout')
  @UseGuards(AuthGuard('jwt'))
  @HttpCode(HttpStatus.OK)
  async logout(
    @Req() req: { user: { sub: string } },
    @Res({ passthrough: true }) res: Response,
  ) {
    const userId = req.user.sub;
    await this.authService.logout(userId);

    res.clearCookie('refresh_token');

    return { message: 'Logged out successfully' };
  }

  @Post('refresh')
  @UseGuards(RefreshTokenGuard)
  async refresh(
    @Req() req: { user: { sub: string; refreshToken: string } },
    @Res({ passthrough: true }) res: Response,
  ) {
    const userId = req.user.sub;
    const token = req.user.refreshToken;
    const tokens = await this.authService.refreshTokenService(userId, token);
    res.cookie('refresh_token', tokens.refresh_token, {
      httpOnly: true,
      secure: true,
      sameSite: 'strict',
      maxAge: 7 * 24 * 60 * 60 * 1000,
    });
    return { access_token: tokens.access_token };
  }

  /**
   * Preview invitation details before acceptance.
   * Returns whether the user already has an account, allowing frontend
   * to show the appropriate form (new user registration vs existing user login).
   */
  @Get('invitations/:token/preview')
  async previewInvitation(@Param('token') invitationToken: string) {
    return this.invitationService.preview(invitationToken);
  }

  /**
   * Accept invitation as a NEW user (no existing account).
   * Creates a new user account and adds them to the organization.
   */
  @Post('invitations/:token/accept/new-user')
  async acceptInvitationAsNewUser(
    @Param('token') invitationToken: string,
    @Body() acceptInvitationDto: AcceptInvitationDTO,
    @Res({ passthrough: true }) res: Response,
  ) {
    const { user, membership } = await this.invitationService.acceptAsNewUser(
      invitationToken,
      acceptInvitationDto,
    );

    const tokens = await this.authService.getTokensForUser(user, membership);
    res.cookie('refresh_token', tokens.refresh_token, {
      httpOnly: true,
      secure: this.configService.get('NODE_ENV') !== 'development',
      sameSite: 'strict',
      maxAge: 7 * 24 * 60 * 60 * 1000,
    });

    return {
      message: `Welcome! Your account has been created and you are now a member.`,
      access_token: tokens.access_token,
      user,
    };
  }

  /**
   * Accept invitation as an EXISTING user.
   * Requires password authentication to verify account ownership.
   * This is the industry-standard approach to prevent unauthorized org additions.
   */
  @Post('invitations/:token/accept/existing-user')
  async acceptInvitationAsExistingUser(
    @Param('token') invitationToken: string,
    @Body() acceptInvitationDto: AcceptInvitationExistingUserDTO,
    @Res({ passthrough: true }) res: Response,
  ) {
    const { user, membership } =
      await this.invitationService.acceptAsExistingUser(
        invitationToken,
        acceptInvitationDto,
      );

    const tokens = await this.authService.getTokensForUser(user, membership);
    res.cookie('refresh_token', tokens.refresh_token, {
      httpOnly: true,
      secure: this.configService.get('NODE_ENV') !== 'development',
      sameSite: 'strict',
      maxAge: 7 * 24 * 60 * 60 * 1000,
    });

    return {
      message: `Welcome back! You have joined the organization.`,
      access_token: tokens.access_token,
      user,
    };
  }

  /**
   * @deprecated Use /accept/new-user or /accept/existing-user instead.
   * Kept for backward compatibility - auto-detects user type.
   */
  @Post('invitations/:token/accept')
  async acceptsInvitation(
    @Param('token') invitationToken: string,
    @Body() acceptInvitationDto: AcceptInvitationDTO,
    @Res({ passthrough: true }) res: Response,
  ) {
    const { user, membership } = await this.invitationService.accept(
      invitationToken,
      acceptInvitationDto,
    );

    const tokens = await this.authService.getTokensForUser(user, membership);
    res.cookie('refresh_token', tokens.refresh_token, {
      httpOnly: true,
      secure: this.configService.get('NODE_ENV') !== 'development',
      sameSite: 'strict',
      maxAge: 7 * 24 * 60 * 60 * 1000,
    });

    return {
      message: `Welcome! You are now a member.`,
      access_token: tokens.access_token,
      user,
    };
  }

  @Post('password-reset-request')
  async PasswordResetRequest(
    @Body() passwordResetRequestDto: PasswordResetRequestDTO,
  ) {
    return await this.authService.handlePasswordResetRequest(
      passwordResetRequestDto.email,
    );
  }

  @Post('password-reset')
  async PasswordReset(@Body() passwordResetDto: PerformPasswordResetDTO) {
    return await this.authService.performPasswordReset(
      passwordResetDto.reset_token,
      passwordResetDto.new_password,
    );
  }

  @UseGuards(AuthGuard('jwt'))
  @Post('token/switch')
  async ContextSwitching(
    @Body() switchOrganizationDto: SwitchOrganizationDTO,
    @Req() req: { user: { sub: string } },
  ) {
    const userId = req.user.sub;
    return await this.authService.switchOrganization(
      userId,
      switchOrganizationDto.organizationId,
    );
  }
}
