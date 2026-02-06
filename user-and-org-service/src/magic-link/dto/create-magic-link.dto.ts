// src/magic-link/dto/create-magic-link.dto.ts
import { IsString, IsNotEmpty, IsUUID, IsDateString } from 'class-validator';

export class CreateMagicLinkDto {
  @IsUUID()
  @IsNotEmpty()
  userId: string;

  @IsUUID()
  @IsNotEmpty()
  sessionId: string;

  @IsUUID()
  @IsNotEmpty()
  eventId: string;

  @IsUUID()
  @IsNotEmpty()
  registrationId: string;

  @IsDateString()
  @IsNotEmpty()
  sessionEndTime: string;
}

export class RevokeMagicLinkDto {
  @IsString()
  jti?: string;

  @IsUUID()
  registrationId?: string;
}
