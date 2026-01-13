// In src/auth/strategies/refresh-token.strategy.ts

import { Injectable } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy } from 'passport-jwt';
import { Request } from 'express';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class RefreshTokenStrategy extends PassportStrategy(
  Strategy,
  'jwt-refresh',
) {
  constructor(configService: ConfigService) {
    const jwtRefreshSecret = configService.get<string>('JWT_REFRESH_SECRET');
    if (!jwtRefreshSecret) {
      throw new Error('JWT_REFRESH_SECRET environment variable is not configured');
    }
    super({
      jwtFromRequest: ExtractJwt.fromExtractors([
        (req: Request) => req?.cookies?.refresh_token
      ]),
      secretOrKey: jwtRefreshSecret,
      passReqToCallback: true,
    });
  }

  validate(
    req: Request,
    payload: { sub: string; email: string; [key: string]: any },
  ) {
    const authHeader = req.get('authorization');
    const refreshToken = authHeader
      ? authHeader.replace('Bearer', '').trim()
      : '';

    return { ...payload, refreshToken };
  }
}
