import { IsString, MinLength, Matches } from 'class-validator';

//src/auth/dto/perform-reset.dto.ts
export class PerformPasswordResetDTO {
  @IsString()
  reset_token: string;

  @IsString()
  @MinLength(8, { message: 'Password must be at least 8 characters long' })
  @Matches(
    /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/,
    { message: 'Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character (@$!%*?&)' }
  )
  new_password: string;
}
