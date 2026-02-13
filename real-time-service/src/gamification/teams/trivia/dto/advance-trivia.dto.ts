// src/gamification/teams/trivia/dto/advance-trivia.dto.ts
import { IsNotEmpty, IsString } from 'class-validator';

export class AdvanceTriviaDto {
  @IsString()
  @IsNotEmpty()
  gameId: string;
}
