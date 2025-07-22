// In src/auth/guards/refresh-token.guard.ts

import { Injectable } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';

@Injectable()
export class RefreshTokenGuard extends AuthGuard('jwt-refresh') {
  // We use 'jwt-refresh' which matches the key name from our strategy
  constructor() {
    super();
  }
}
