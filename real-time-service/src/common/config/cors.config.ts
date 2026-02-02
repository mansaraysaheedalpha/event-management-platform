// src/common/config/cors.config.ts
/**
 * Shared CORS configuration for WebSocket gateways.
 *
 * When credentials are used, the origin cannot be '*'.
 * Reads from CORS_ORIGINS or ALLOWED_ORIGINS environment variable for consistency.
 *
 * Supports wildcard patterns (e.g., "*.example.com" matches "app.example.com")
 */

/**
 * Check if an origin matches an allowed origin pattern.
 * Supports exact matches and wildcard patterns (e.g., "*.example.com")
 */
function matchesOrigin(origin: string, pattern: string): boolean {
  // Exact match
  if (origin === pattern) {
    return true;
  }

  // Wildcard pattern (e.g., "*.example.com")
  if (pattern.startsWith('*.')) {
    const suffix = pattern.slice(1); // ".example.com"
    // Origin should end with the suffix (e.g., "app.example.com" ends with ".example.com")
    // Also check the base domain (e.g., "example.com" without subdomain)
    const baseDomain = pattern.slice(2); // "example.com"
    const originHost = new URL(origin).host;
    return originHost.endsWith(suffix) || originHost === baseDomain;
  }

  return false;
}

/**
 * Get allowed origins from environment variables.
 * Checks both CORS_ORIGINS and ALLOWED_ORIGINS for backwards compatibility.
 */
export function getAllowedOriginsList(): string[] {
  const corsOrigins = process.env.CORS_ORIGINS || process.env.ALLOWED_ORIGINS;

  if (!corsOrigins) {
    // Default to localhost in development
    if (process.env.NODE_ENV === 'development') {
      return [
        'http://localhost:3000',
        'http://localhost:3001',
        'http://127.0.0.1:3000',
        'http://127.0.0.1:3001',
      ];
    }
    return [];
  }

  return corsOrigins.split(',').map((origin) => origin.trim()).filter(Boolean);
}

export function getCorsConfig() {
  const allowedOrigins = getAllowedOriginsList();

  return {
    origin: allowedOrigins.length > 0 ? allowedOrigins : false,
    credentials: true,
  };
}

/**
 * Static CORS config for use in decorators.
 * Since decorators are evaluated at class definition time (before env vars are loaded),
 * we need to use a function that validates origin dynamically.
 *
 * SECURITY: In production, rejects origins not in the allowed list.
 */
export const WEBSOCKET_CORS_CONFIG = {
  origin: (origin: string | undefined, callback: (err: Error | null, allow?: boolean) => void) => {
    // Allow requests with no origin (like mobile apps, curl, Postman, etc.)
    if (!origin) {
      callback(null, true);
      return;
    }

    const allowedOrigins = getAllowedOriginsList();

    // In development with no configured origins, allow localhost
    const isProduction = process.env.NODE_ENV === 'production';

    // Check if origin matches any allowed pattern
    const isAllowed = allowedOrigins.some((pattern) => matchesOrigin(origin, pattern));

    if (isAllowed) {
      callback(null, true);
    } else if (!isProduction && allowedOrigins.length === 0) {
      // In development with no config, allow all for easier testing
      console.warn(`[CORS] Development mode: allowing origin ${origin}`);
      callback(null, true);
    } else {
      // SECURITY: Reject unknown origins in production
      console.warn(
        `[CORS] Origin ${origin} rejected. Allowed: ${allowedOrigins.join(', ') || 'none configured'}`,
      );
      callback(new Error('CORS origin not allowed'), false);
    }
  },
  credentials: true,
};
