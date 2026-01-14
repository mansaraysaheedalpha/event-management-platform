//src/invitations/dto/AcceptInvitationExistingUserDTO.ts
import { MinLength, IsNotEmpty, IsString, Matches } from 'class-validator';

/**
 * DTO for existing users accepting an invitation.
 * Only requires password for authentication - user already has an account.
 */
export class AcceptInvitationExistingUserDTO {
  @IsString()
  @IsNotEmpty()
  @MinLength(8, { message: 'Password must be at least 8 characters long' })
  password: string;
}
