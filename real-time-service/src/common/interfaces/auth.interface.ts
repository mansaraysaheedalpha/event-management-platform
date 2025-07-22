import { Socket } from 'socket.io';

// 1. Define the shape of our token's payload
export interface JwtPayload {
  sub: string;
  email: string;
  orgId: string; // <-- The user's active Organization ID, need to update this change in the user's microservice
  role?: string; // Optional: for role-based access
  permissions?: string[];
  preferredLanguage?: string;
}

// 2. Define the shape of our authenticated socket
export interface AuthenticatedSocket extends Socket {
  data: {
    user: JwtPayload;
  };
}
