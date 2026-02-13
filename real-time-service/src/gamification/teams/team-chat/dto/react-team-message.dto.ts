// src/gamification/teams/team-chat/dto/react-team-message.dto.ts
import { IsNotEmpty, IsString, MaxLength } from 'class-validator';

export class ReactTeamMessageDto {
  @IsNotEmpty()
  @IsString()
  teamId: string;

  @IsNotEmpty()
  @IsString()
  messageId: string;

  @IsString()
  @IsNotEmpty()
  @MaxLength(8)
  emoji: string;

  @IsNotEmpty()
  @IsString()
  idempotencyKey: string;
}
