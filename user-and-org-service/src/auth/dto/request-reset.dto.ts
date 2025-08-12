import { IsEmail, IsNotEmpty } from 'class-validator';

//src/auth/dto/request-reset.dto.ts
export class PasswordResetRequestDTO {
  @IsEmail()
  @IsNotEmpty()
  email: string;
}
