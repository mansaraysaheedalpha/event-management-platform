import { IsEmail, IsNotEmpty, IsString } from 'class-validator';

// In src/auth/dto/login.dto.ts
export class LoginDTO {
  @IsEmail()
  @IsNotEmpty()
  email: string;

  @IsString()
  @IsNotEmpty()
  password: string;
}
