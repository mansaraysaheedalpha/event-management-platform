import { Socket } from 'socket.io';
import { AuthenticatedSocket, JwtPayload } from '../interfaces/auth.interface';
import { UnauthorizedException } from '@nestjs/common';

/**
 * Safely extracts the JWT token from a Socket.IO client's handshake.
 * Checks multiple possible locations: `auth.token` header or query string.
 *
 * @param client - The Socket.IO client instance.
 * @returns The extracted token string, or null if none found.
 */
export const extractTokenSafely = (client: Socket): string | null => {
  const authHeader = client.handshake.auth;
  if (authHeader && typeof authHeader.token === 'string') {
    return authHeader.token.replace('Bearer', '').trim();
  }

  const queryToken = client.handshake.query?.token;
  if (typeof queryToken === 'string') {
    return queryToken;
  }

  if (Array.isArray(queryToken) && queryToken.length > 0) {
    return queryToken[0];
  }

  return null;
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
