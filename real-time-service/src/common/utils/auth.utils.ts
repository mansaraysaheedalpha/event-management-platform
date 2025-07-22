import { Socket } from 'socket.io';
import { AuthenticatedSocket, JwtPayload } from '../interfaces/auth.interface';
import { UnauthorizedException } from '@nestjs/common';

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

export const getAuthenticatedUser = (
  client: AuthenticatedSocket,
): JwtPayload => {
  if (!client.data.user) {
    throw new UnauthorizedException('User not authenticated');
  }
  return client.data.user;
};
