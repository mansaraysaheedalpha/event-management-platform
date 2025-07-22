import { IsNotEmpty, IsString, Length } from 'class-validator';

// In src/auth/dto/login-2fa.dto.ts
export class Login2faDto {
  @IsString()
  @IsNotEmpty()
  userId: string;

  @IsString()
  @IsNotEmpty()
  @Length(6, 6)
  code: string;
}
