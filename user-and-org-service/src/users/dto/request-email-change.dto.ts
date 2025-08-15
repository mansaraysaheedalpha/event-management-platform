// src/users/dto/register-email-change.dto.ts
import { IsEmail, IsNotEmpty } from 'class-validator';

export class RequestEmailChangeDto {
  @IsEmail()
  @IsNotEmpty()
  newEmail: string;
}
