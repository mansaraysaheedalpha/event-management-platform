// src/gamification/teams/team-chat/dto/send-team-message.dto.ts
import {
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUUID,
  MaxLength,
} from 'class-validator';

export class SendTeamMessageDto {
  @IsNotEmpty()
  @IsString()
  teamId: string;

  @IsString()
  @IsNotEmpty()
  @MaxLength(1000)
  text: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;

  /** Optional JSON metadata (e.g., link previews, embedded content). */
  @IsOptional()
  metadata?: Record<string, any>;
}
