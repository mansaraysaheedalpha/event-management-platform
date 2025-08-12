//src/common/interfaces/security.interface.ts
/**
 * Represents security-related events emitted by the system for logging or alerting.
 *
 * Examples:
 * - Brute-force attack detected on a user account
 * - Unusual login from a new IP/device
 * - Changes to permissions
 */
export interface SecurityAlertPayload {
  type: 'BRUTE_FORCE_SUSPECTED' | 'UNUSUAL_LOGIN' | 'PERMISSION_CHANGE';
  actingUserId: string;
  organizationId: string;
  details?: Record<string, any>; // e.g., { ip: '196.123.12.1', userAgent: '...' }
}

// --- NEW, COMPLETE PAYLOADS ---
export interface AccessControlUpdatePayload {
  type: 'ACCESS_CONTROL_UPDATE';
  organizationId: string;
  actingUserId: string; // Admin who made the change
  targetUserId: string; // User whose permissions changed
  permissionsGranted?: string[];
  permissionsRevoked?: string[];
}

export interface SessionConflictPayload {
  type: 'SESSION_CONFLICT_DETECTED';
  organizationId: string;
  conflictingSessionIds: string[];
  resolutionSuggestion: string;
}

// A union type that represents any possible security event
export type SecurityEventPayload =
  | SecurityAlertPayload
  | AccessControlUpdatePayload
  | SessionConflictPayload;

