/**
 * Structure for recording actions into your audit logging system.
 * Helps track who did what, when, and in what context (e.g. session or org).
 *
 * Example:
 * {
 *   action: 'SESSION_DELETED',
 *   actingUserId: 'user-123',
 *   organizationId: 'org-456',
 *   sessionId: 'session-789',
 *   details: { reason: 'Moderator decision' }
 * }
 */
export interface AuditLogPayload<DetailsType = Record<string, unknown>> {
  action: string;
  actingUserId: string;
  organizationId: string;
  sessionId?: string;
  details?: DetailsType;
}
