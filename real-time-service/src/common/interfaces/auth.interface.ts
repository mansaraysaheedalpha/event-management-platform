//src/common/interfaces/auth.interface.ts
import { Socket } from 'socket.io';

/**
 * Standard payload extracted from the user's JWT.
 * Used to identify and authorize users across microservices.
 */
export interface JwtPayload {
  sub: string; // User ID
  email: string;
  orgId: string; // Active organization context
  role?: string;
  permissions?: string[];
  tier?: 'default' | 'vip';
  preferredLanguage?: string;
  sponsorId?: string;
}

/**
 * A WebSocket client that has passed authentication.
 * Carries the validated JwtPayload for authorization purposes during communication.
 *
 * Usage:
 * const user = client.data.user;
 */
export interface AuthenticatedSocket extends Socket {
  data: {
    user: JwtPayload;
  };
}
