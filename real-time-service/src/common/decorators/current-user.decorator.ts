// src/common/decorators/current-user.decorator.ts
import { createParamDecorator, ExecutionContext } from '@nestjs/common';

/**
 * Decorator to extract the current authenticated user from the request.
 * Works with JwtAuthGuard which attaches the user to the request object.
 *
 * Usage:
 * @Get('profile')
 * getProfile(@CurrentUser() user: JwtUser) {
 *   return user;
 * }
 */
export const CurrentUser = createParamDecorator(
  (data: string | undefined, ctx: ExecutionContext) => {
    const request = ctx.switchToHttp().getRequest();
    const user = request.user;

    // If a specific property is requested, return just that
    if (data && user) {
      return user[data];
    }

    return user;
  },
);
