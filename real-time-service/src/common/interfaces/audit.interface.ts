export interface AuditLogPayload {
  action: string; // e.g., 'POLL_CLOSED', 'MESSAGE_DELETED'
  actingUserId: string;
  organizationId: string;
  sessionId?: string;
  details?: Record<string, any>; // For extra context, e.g., { "deletedMessageId": "..." }
}
