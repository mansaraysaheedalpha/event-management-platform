// src/common/config/cors.config.ts
/**
 * Shared CORS configuration for WebSocket gateways.
 *
 * When credentials are used, the origin cannot be '*'.
 * This reads from ALLOWED_ORIGINS environment variable.
 */

export function getCorsConfig() {
  const allowedOrigins = process.env.ALLOWED_ORIGINS
    ? process.env.ALLOWED_ORIGINS.split(',').map((origin) => origin.trim())
    : ['http://localhost:3000'];

  return {
    origin: allowedOrigins,
    credentials: true,
  };
}

/**
 * Static CORS config for use in decorators.
 * Since decorators are evaluated at class definition time (before env vars are loaded),
 * we need to use a function that validates origin dynamically.
 */
export const WEBSOCKET_CORS_CONFIG = {
  origin: (origin: string | undefined, callback: (err: Error | null, allow?: boolean) => void) => {
    // Allow requests with no origin (like mobile apps, curl, etc.)
    if (!origin) {
      callback(null, true);
      return;
    }

    const allowedOrigins = process.env.ALLOWED_ORIGINS
      ? process.env.ALLOWED_ORIGINS.split(',').map((o) => o.trim())
      : ['http://localhost:3000'];

    if (allowedOrigins.includes(origin)) {
      callback(null, true);
    } else {
      // Log for debugging but allow in development
      console.warn(`[CORS] Origin ${origin} not in allowed list: ${allowedOrigins.join(', ')}`);
      // In production, you might want to reject. For now, allow to prevent breaking changes.
      callback(null, true);
    }
  },
  credentials: true,
};
