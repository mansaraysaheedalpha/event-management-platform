/**
 * Contains minimal info about the user who owns a validated ticket.
 *
 * Example:
 * {
 *   id: 'user-123',
 *   name: 'Alice Kamara',
 *   avatarUrl: 'https://cdn.app.com/avatar.png'
 * }
 */
export class ValidatedUserDto {
  /** Unique user ID */
  id: string;

  /** Full name of the user */
  name: string;

  /** Optional URL to the user's avatar */
  avatarUrl?: string;
}

/**
 * The final result after ticket validation. Returned to the gateway or client.
 *
 * Example:
 * {
 *   isValid: true,
 *   ticketCode: 'ABC123',
 *   validatedAt: '2025-07-23T22:10:00Z',
 *   user: { id: 'u-1', name: 'John', avatarUrl: '...' },
 *   accessLevel: 'VIP',
 * }
 */
export class ValidationResultDto {
  /** True if the ticket is valid */
  isValid: boolean;

  /** The ticket code that was validated */
  ticketCode: string;

  /** ISO timestamp of validation */
  validatedAt: string;

  /** Info about the user, if ticket is linked */
  user?: ValidatedUserDto;

  /** Optional access level (e.g., VIP, General) */
  accessLevel?: string;

  /** If invalid, reason for rejection (e.g., "expired") */
  errorReason?: string;
}
