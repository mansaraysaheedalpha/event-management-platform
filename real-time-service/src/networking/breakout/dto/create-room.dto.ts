// src/networking/breakout/dto/create-room.dto.ts
import { IsString, IsOptional, IsInt, IsBoolean, Min, Max, MaxLength } from 'class-validator';

export class CreateRoomDto {
  @IsString()
  sessionId: string;

  @IsString()
  eventId: string;

  @IsString()
  @MaxLength(100)
  name: string;

  @IsOptional()
  @IsString()
  @MaxLength(500)
  topic?: string;

  @IsOptional()
  @IsInt()
  @Min(2)
  @Max(50)
  maxParticipants?: number;

  @IsOptional()
  @IsInt()
  @Min(5)
  @Max(120)
  durationMinutes?: number;

  @IsOptional()
  @IsBoolean()
  autoAssign?: boolean;

  @IsOptional()
  @IsString()
  facilitatorId?: string;

  @IsOptional()
  @IsString()
  idempotencyKey?: string;
}
