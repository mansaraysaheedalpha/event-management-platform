// src/gamification/teams/trivia/dto/end-trivia.dto.ts
import { IsNotEmpty, IsString } from 'class-validator';

export class EndTriviaDto {
  @IsString()
  @IsNotEmpty()
  gameId: string;
}
