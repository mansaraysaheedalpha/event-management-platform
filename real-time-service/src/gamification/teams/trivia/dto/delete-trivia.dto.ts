// src/gamification/teams/trivia/dto/delete-trivia.dto.ts
import { IsNotEmpty, IsString } from 'class-validator';

export class DeleteTriviaDto {
  @IsString()
  @IsNotEmpty()
  gameId: string;
}
