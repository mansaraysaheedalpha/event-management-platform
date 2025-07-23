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
