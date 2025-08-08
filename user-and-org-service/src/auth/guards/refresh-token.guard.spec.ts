import { RefreshTokenGuard } from './refresh-token.guard';

// In src/auth/guards/refresh-token.guard.spec.ts

describe('RefreshTokenGuard', () => {
  it('should be defined', () => {
    expect(new RefreshTokenGuard()).toBeDefined();
  });
});
