import { IsString, MinLength } from 'class-validator';

export class PerformPasswordResetDTO {
  @IsString()
  reset_token: string;

  @IsString()
  @MinLength(8, { message: 'password must be at least 8 characters long' })
  new_password: string;
}
