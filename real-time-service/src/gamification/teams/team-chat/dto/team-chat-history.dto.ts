// src/gamification/teams/team-chat/dto/team-chat-history.dto.ts
import {
  IsNotEmpty,
  IsOptional,
  IsString,
  IsInt,
  Min,
  Max,
} from 'class-validator';
import { Type } from 'class-transformer';

export class TeamChatHistoryDto {
  @IsNotEmpty()
  @IsString()
  teamId: string;

  /** Cursor: load messages before this message ID (for pagination). */
  @IsOptional()
  @IsString()
  before?: string;

  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  limit?: number;
}
