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
    // Only set CSRF cookie if it doesn't exist or for authenticated requests
    if (!req.cookies[CSRF_COOKIE_NAME]) {
      const token = this.csrfService.generateToken();

      res.cookie(CSRF_COOKIE_NAME, token, {
        httpOnly: false, // Must be readable by JavaScript to send in header
        secure: this.configService.get('NODE_ENV') !== 'development',
        sameSite: 'lax', // Changed from 'strict' to allow cross-site requests with cookies
        maxAge: 24 * 60 * 60 * 1000, // 24 hours
        path: '/',
      });
    }

    next();
  }
}
