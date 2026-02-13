// src/gamification/teams/challenges/dto/cancel-challenge.dto.ts
import { IsNotEmpty, IsString } from 'class-validator';

export class CancelChallengeDto {
  @IsString()
  @IsNotEmpty()
  challengeId: string;

  @IsString()
  @IsNotEmpty()
  idempotencyKey: string;
}
