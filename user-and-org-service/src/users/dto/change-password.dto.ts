//src/users/dto/change-password.dto.ts
import { IsString, MaxLength, MinLength, Matches } from 'class-validator';

export class ChangePasswordDTO {
  @IsString()
  currentPassword: string;

  @IsString()
  @MinLength(8, { message: 'Password should be at least 8 characters long' })
  @MaxLength(64, { message: 'New password must be at most 64 characters long' })
  @Matches(
    /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/,
    { message: 'Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character (@$!%*?&)' }
  )
  newPassword: string;
}
