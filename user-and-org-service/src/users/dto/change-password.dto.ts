//src/users/dto/change-password.dto.ts
import { IsString, MaxLength, MinLength } from 'class-validator';

export class ChangePasswordDTO {
  @IsString()
  currentPassword: string;

  @IsString()
  @MinLength(8, { message: 'Password should be at least 8 characters long' })
  @MaxLength(64, { message: 'New password must be at most 64 characters long' })
  newPassword: string;
}
