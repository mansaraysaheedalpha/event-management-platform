// src/common/csrf/csrf.middleware.ts
import { Injectable, NestMiddleware } from '@nestjs/common';
import { Request, Response, NextFunction } from 'express';
import { ConfigService } from '@nestjs/config';
import { CsrfService } from './csrf.service';

export const CSRF_COOKIE_NAME = 'csrf_token';
export const CSRF_HEADER_NAME = 'x-csrf-token';

@Injectable()
export class CsrfMiddleware implements NestMiddleware {
  constructor(
    private readonly csrfService: CsrfService,
    private readonly configService: ConfigService,
  ) {}

  use(req: Request, res: Response, next: NextFunction) {
    // Get existing token or generate a new one
    let token = req.cookies[CSRF_COOKIE_NAME];

    if (!token) {
      token = this.csrfService.generateToken();

      res.cookie(CSRF_COOKIE_NAME, token, {
        httpOnly: false, // Must be readable by JavaScript to send in header
        secure: this.configService.get('NODE_ENV') !== 'development',
        sameSite: this.configService.get('NODE_ENV') === 'development' ? 'lax' : 'none', // 'none' required for cross-domain (Vercel→Render)
        maxAge: 24 * 60 * 60 * 1000, // 24 hours
        path: '/',
      });
    }

    // CRITICAL: Send token in response header for cross-origin setups
    // Frontend JavaScript can't read cross-domain cookies, so we expose it via header
    res.setHeader('X-CSRF-Token', token);

    next();
  }
}
