//src/common/utils/auth.utils.ts
import { Socket } from 'socket.io';
import { AuthenticatedSocket, JwtPayload } from '../interfaces/auth.interface';
import { UnauthorizedException } from '@nestjs/common';

// Re-export types for convenience
export { AuthenticatedSocket, JwtPayload };

/**
 * Safely extracts the JWT token from a Socket.IO client's handshake.
 * Only accepts tokens from the `auth.token` property (set via Socket.IO auth option).
 * Query string fallback was removed to prevent token exposure in URLs and server logs.
 *
 * @param client - The Socket.IO client instance.
 * @returns The extracted token string, or null if none found.
 */
export const extractTokenSafely = (client: Socket): string | null => {
  try {
    const auth = client.handshake?.auth;
    if (auth?.token && typeof auth.token === 'string') {
      return auth.token.replace('Bearer ', '').trim();
    }
    // Query string fallback intentionally removed (security risk - tokens in URLs/logs)
    return null;
  } catch {
    return null;
  }
};

/**
 * Retrieves the authenticated user's JWT payload from a socket's stored data.
 * Throws an UnauthorizedException if no user data is found.
 *
 * @param client - The authenticated Socket.IO client.
 * @returns The JWT payload of the authenticated user.
 * @throws UnauthorizedException If user is not authenticated.
 */
export const getAuthenticatedUser = (
  client: AuthenticatedSocket,
): JwtPayload => {
  if (!client.data.user) {
    throw new UnauthorizedException('User not authenticated');
  }
  return client.data.user;
};
