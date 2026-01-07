// src/common/csrf/csrf.guard.ts
import {
  Injectable,
  CanActivate,
  ExecutionContext,
  ForbiddenException,
} from '@nestjs/common';
import { GqlExecutionContext } from '@nestjs/graphql';
import { CsrfService } from './csrf.service';
import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME } from './csrf.middleware';

@Injectable()
export class CsrfGuard implements CanActivate {
  constructor(private readonly csrfService: CsrfService) {}

  canActivate(context: ExecutionContext): boolean {
    const gqlContext = GqlExecutionContext.create(context);
    const { req } = gqlContext.getContext();

    // Skip CSRF check for introspection queries (development only)
    const info = gqlContext.getInfo();
    if (info?.fieldName === '__schema' || info?.fieldName === '__type') {
      return true;
    }

    const cookieToken = req.cookies?.[CSRF_COOKIE_NAME];
    const headerToken = req.headers?.[CSRF_HEADER_NAME];

    if (!this.csrfService.validateToken(cookieToken, headerToken)) {
      throw new ForbiddenException('CSRF validation failed');
    }

    return true;
  }
}
