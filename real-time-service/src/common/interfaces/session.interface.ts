//src/common/interfaces/session.interface.ts
/**
 * Attached to any socket or event to provide context about the current session.
 */
export interface SessionMetadata {
  eventId: string;
  organizationId: string;
}
