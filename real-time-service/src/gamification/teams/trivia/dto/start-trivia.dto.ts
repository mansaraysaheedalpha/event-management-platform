// src/gamification/teams/trivia/dto/start-trivia.dto.ts
import { IsNotEmpty, IsString } from 'class-validator';

export class StartTriviaDto {
  @IsString()
  @IsNotEmpty()
  gameId: string;
}
