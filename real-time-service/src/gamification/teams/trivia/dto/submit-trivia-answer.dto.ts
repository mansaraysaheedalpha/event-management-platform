// src/gamification/teams/trivia/dto/submit-trivia-answer.dto.ts
import { IsNotEmpty, IsString, IsInt, Min, Max } from 'class-validator';

export class SubmitTriviaAnswerDto {
  @IsString()
  @IsNotEmpty()
  gameId: string;

  @IsString()
  @IsNotEmpty()
  questionId: string;

  @IsString()
  @IsNotEmpty()
  teamId: string;

  @IsInt()
  @Min(0)
  @Max(9) // Max 10 options (0-indexed), enforced at DTO level; service also validates against question.options.length
  selectedIndex: number;

  @IsString()
  @IsNotEmpty()
  idempotencyKey: string;
}
