import { UnauthorizedException } from '@nestjs/common';
import { AuthenticatedSocket, JwtPayload } from '../interfaces/auth.interface';
import { getAuthenticatedUser } from './auth.utils';

describe('auth.utils', () => {
  describe('getAuthenticatedUser', () => {
    it('should return the user payload if it exists on the socket data', () => {
      const mockUser: JwtPayload = {
        sub: 'user-123',
        email: 'test@example.com',
        orgId: 'org-abc',
      };
      const mockClient: AuthenticatedSocket = {
        data: { user: mockUser },
      } as any; // Cast to 'any' to simplify the mock

      const result = getAuthenticatedUser(mockClient);
      expect(result).toEqual(mockUser);
    });

    it('should throw UnauthorizedException if user data is missing', () => {
      const mockClient: AuthenticatedSocket = {
        data: {}, // No user property
      } as any;

      expect(() => getAuthenticatedUser(mockClient)).toThrow(
        UnauthorizedException,
      );
    });
  });
});
