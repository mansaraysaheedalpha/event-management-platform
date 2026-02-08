// src/virtual-stage/dto/create-stage-room.dto.ts
import { IsString, IsOptional, IsInt, IsBoolean, Min, Max, MaxLength } from 'class-validator';

export class CreateStageRoomDto {
  @IsString()
  sessionId: string;

  @IsString()
  @MaxLength(200)
  sessionTitle: string;

  @IsString()
  eventId: string;

  @IsOptional()
  @IsInt()
  @Min(2)
  @Max(1000)
  maxParticipants?: number;

  @IsOptional()
  @IsInt()
  @Min(30)
  @Max(720)
  expiryMinutes?: number;

  @IsOptional()
  @IsBoolean()
  enableRecording?: boolean;
}
