// src/common/csrf/csrf.service.ts
import { Injectable } from '@nestjs/common';
import { randomBytes, timingSafeEqual } from 'crypto';

@Injectable()
export class CsrfService {
  private readonly TOKEN_LENGTH = 32;

  /**
   * Generate a cryptographically secure CSRF token
   */
  generateToken(): string {
    return randomBytes(this.TOKEN_LENGTH).toString('hex');
  }

  /**
   * Validate CSRF token using timing-safe comparison
   */
  validateToken(cookieToken: string | undefined, headerToken: string | undefined): boolean {
    if (!cookieToken || !headerToken) {
      return false;
    }

    // Ensure both tokens are the same length before comparison
    if (cookieToken.length !== headerToken.length) {
      return false;
    }

    try {
      const cookieBuffer = Buffer.from(cookieToken, 'utf8');
      const headerBuffer = Buffer.from(headerToken, 'utf8');
      return timingSafeEqual(cookieBuffer, headerBuffer);
    } catch {
      return false;
    }
  }
}
