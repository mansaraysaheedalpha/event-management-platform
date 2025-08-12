// In src/auth/guards/roles.guard.spec.ts
import { RolesGuard } from './roles.guard';

describe('RolesGuard', () => {
  it('should be defined', () => {
    expect(new RolesGuard()).toBeDefined();
  });
});
