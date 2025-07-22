import { IsEmail, IsNotEmpty } from 'class-validator';

export class RequestEmailChangeDto {
  @IsEmail()
  @IsNotEmpty()
  newEmail: string;
}
