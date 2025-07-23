/**
 * Data Transfer Object (DTO) for an audit log entry.
 * Used to structure audit log data exchanged between services and clients.
 *
 * @example
 * const auditLog: AuditLogDto = {
 *   id: 'log123',
 *   action: 'USER_BANNED',
 *   actingUserId: 'admin456',
 *   organizationId: 'org789',
 *   targetUserId: 'user001',
 *   details: { reason: 'TOS violation' },
 *   createdAt: new Date(),
 * };
 */
export class AuditLogDto {
  /**
   * Unique ID of the audit log entry.
   */
  id: string;

  /**
   * Describes the action performed (e.g., 'USER_BANNED', 'ORG_UPDATED').
   */
  action: string;

  /**
   * The ID of the user who triggered the action.
   */
  actingUserId: string;

  /**
   * The organization where the action occurred.
   */
  organizationId: string;

  /**
   * (Optional) The user affected by the action, if applicable.
   */
  targetUserId: string;

  /**
   * Additional contextual information about the action.
   */
  details: JSON;

  /**
   * Timestamp when the log entry was created.
   */
  createdAt: Date;
}
