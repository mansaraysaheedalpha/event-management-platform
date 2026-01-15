// src/common/guards/jwt-auth.guard.ts
import {
  ExecutionContext,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';

/**
 * JWT Authentication Guard for REST endpoints.
 * Uses the 'jwt' strategy registered by AccessTokenStrategy.
 */
@Injectable()
export class JwtAuthGuard extends AuthGuard('jwt') {
  /**
   * Provides better error handling for authentication failures.
   */
  handleRequest<TUser = any>(
    err: any,
    user: TUser,
    info: any,
    context: ExecutionContext,
  ): TUser {
    if (err || !user) {
      // Log the detailed error on the server for debugging
      console.error('JWT Auth Error:', info?.message || err?.message);
      throw err || new UnauthorizedException('Invalid or expired token');
    }
    return user;
  }
}
