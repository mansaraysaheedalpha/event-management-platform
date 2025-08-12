//src/live/validation/dto/validate-result.dto.ts
import { Type } from 'class-transformer';
/**
 * Contains minimal info about the user who owns a validated ticket.
 *
 * Example:
 * {
 *   "id": "user-123",
 *   "name": "Alice Kamara",
 *   "avatarUrl": "https://cdn.app.com/avatar.png"
 * }
 */
export class ValidatedUserDto {
  /** Unique user ID */
  readonly id: string;

  /** Full name of the user */
  readonly name: string;

  /** Optional URL to the user's avatar */
  readonly avatarUrl?: string;
}

/**
 * The final result after ticket validation. Returned to the gateway or client.
 *
 * Example:
 * {
 *   "isValid": true,
 *   "ticketCode": "ABC123",
 *   "validatedAt": "2025-07-23T22:10:00Z",
 *   "user": { "id": "u-1", "name": "John", "avatarUrl": "..." },
 *   "accessLevel": "VIP",
 *   "errorReason": null
 * }
 */
export class ValidationResultDto {
  /** True if the ticket is valid */
  readonly isValid: boolean;

  /** The ticket code that was validated */
  readonly ticketCode: string;

  /** ISO timestamp of validation */
  @Type(() => Date)
  readonly validatedAt: Date;

  /** Info about the user, if ticket is linked */
  readonly user?: ValidatedUserDto;

  /** Optional access level (e.g., VIP, General) */
  readonly accessLevel?: string;

  /** If invalid, reason for rejection (e.g., "expired") */
  readonly errorReason?: string;
}
