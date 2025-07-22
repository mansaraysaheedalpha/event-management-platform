// In src/invitations/dto/create-invitation.dto.ts

import { IsEmail, IsNotEmpty, IsEnum } from 'class-validator';
import { Role } from '@prisma/client';

export class CreateInvitationDto {
  @IsEmail()
  @IsNotEmpty()
  email: string;

  @IsEnum(Role)
  @IsNotEmpty()
  role: Role;
}
