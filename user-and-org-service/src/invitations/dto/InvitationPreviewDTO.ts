//src/invitations/dto/InvitationPreviewDTO.ts

/**
 * Response DTO for invitation preview endpoint.
 * Provides frontend with information needed to show the appropriate acceptance form.
 */
export class InvitationPreviewResponseDTO {
  /** The email address the invitation was sent to */
  email: string;

  /** Name of the organization the user is being invited to */
  organizationName: string;

  /** Name of the person who sent the invitation */
  inviterName: string;

  /** The role the user will be assigned upon acceptance */
  roleName: string;

  /** Whether a user account already exists for this email */
  userExists: boolean;

  /** If user exists, their first name (for personalized greeting) */
  existingUserFirstName?: string;

  /** Invitation expiration timestamp */
  expiresAt: Date;
}
