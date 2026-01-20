// src/expo/dto/booth-video.dto.ts
import { IsString, IsOptional, MaxLength, IsUUID } from 'class-validator';

export class RequestVideoCallDto {
  @IsUUID()
  boothId: string;

  @IsOptional()
  @IsString()
  @MaxLength(500)
  message?: string;
}

export class AcceptVideoCallDto {
  @IsUUID()
  sessionId: string;
}

export class DeclineVideoCallDto {
  @IsUUID()
  sessionId: string;

  @IsOptional()
  @IsString()
  @MaxLength(200)
  reason?: string;
}

export class EndVideoCallDto {
  @IsUUID()
  sessionId: string;
}

export class AddVideoNotesDto {
  @IsUUID()
  sessionId: string;

  @IsString()
  @MaxLength(5000)
  notes: string;
}
