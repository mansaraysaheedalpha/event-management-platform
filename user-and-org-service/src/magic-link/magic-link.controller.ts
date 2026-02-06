// src/magic-link/magic-link.controller.ts
import {
  Controller,
  Post,
  Get,
  Body,
  Query,
  HttpCode,
  HttpStatus,
  UseGuards,
  Res,
  Logger,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Response } from 'express';
import { Throttle } from '@nestjs/throttler';
import { MagicLinkService } from './magic-link.service';
import { CreateMagicLinkDto, RevokeMagicLinkDto } from './dto/create-magic-link.dto';
import { ValidateMagicLinkDto } from './dto/validate-magic-link.dto';
import { InternalApiKeyGuard } from 'src/auth/guards/internal-api-key.guard';

@Controller('auth/magic-link')
export class MagicLinkController {
  private readonly logger = new Logger(MagicLinkController.name);

  constructor(
    private readonly magicLinkService: MagicLinkService,
    private readonly configService: ConfigService,
  ) {}

  /**
   * Generate a magic link for session joining
   * Internal service-to-service endpoint (API key auth)
   */
  @Post('generate')
  @UseGuards(InternalApiKeyGuard)
  @HttpCode(HttpStatus.CREATED)
  async generate(@Body() dto: CreateMagicLinkDto) {
    this.logger.log(`Generating magic link for user ${dto.userId}, session ${dto.sessionId}`);

    const result = await this.magicLinkService.generateSessionJoinLink({
      userId: dto.userId,
      sessionId: dto.sessionId,
      eventId: dto.eventId,
      registrationId: dto.registrationId,
      sessionEndTime: new Date(dto.sessionEndTime),
    });

    return {
      token: result.token,
      url: result.url,
      expiresAt: result.expiresAt.toISOString(),
    };
  }

  /**
   * Validate a magic link token and return auth credentials
   * Public endpoint - token is the auth
   */
  @Get('validate')
  @Throttle({ default: { ttl: 60000, limit: 20 } }) // 20 validations per minute per IP
  @HttpCode(HttpStatus.OK)
  async validate(
    @Query() query: ValidateMagicLinkDto,
    @Res({ passthrough: true }) res: Response,
  ) {
    this.logger.log('Validating magic link token');

    const result = await this.magicLinkService.validateAndAuthenticate(query.token);

    if (!result.valid) {
      return {
        valid: false,
        error: result.error,
      };
    }

    // Set refresh token as HTTP-only cookie
    if (result.refreshToken) {
      res.cookie('refresh_token', result.refreshToken, {
        httpOnly: true,
        secure: this.configService.get('NODE_ENV') !== 'development',
        sameSite: 'strict',
        maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
      });
    }

    return {
      valid: true,
      accessToken: result.accessToken,
      user: result.user,
      redirect: result.redirect,
    };
  }

  /**
   * Revoke magic link token(s)
   * Internal service-to-service endpoint (API key auth)
   */
  @Post('revoke')
  @UseGuards(InternalApiKeyGuard)
  @HttpCode(HttpStatus.OK)
  async revoke(@Body() dto: RevokeMagicLinkDto) {
    if (dto.jti) {
      this.logger.log(`Revoking magic link token: ${dto.jti}`);
      await this.magicLinkService.revoke(dto.jti);
      return { success: true, message: 'Token revoked' };
    }

    if (dto.registrationId) {
      this.logger.log(`Revoking all magic links for registration: ${dto.registrationId}`);
      await this.magicLinkService.revokeAllForRegistration(dto.registrationId);
      return { success: true, message: 'All tokens for registration revoked' };
    }

    return { success: false, message: 'Either jti or registrationId must be provided' };
  }

  /**
   * Check token status without consuming it
   * Internal service-to-service endpoint (API key auth)
   */
  @Get('status')
  @UseGuards(InternalApiKeyGuard)
  @HttpCode(HttpStatus.OK)
  async checkStatus(@Query('jti') jti: string) {
    if (!jti) {
      return { error: 'jti query parameter is required' };
    }

    const status = await this.magicLinkService.checkTokenStatus(jti);
    return status;
  }
}
