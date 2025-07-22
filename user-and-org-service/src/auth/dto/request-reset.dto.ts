import { IsEmail, IsNotEmpty } from 'class-validator';

export class PasswordResetRequestDTO {
  @IsEmail()
  @IsNotEmpty()
  email: string;
}
