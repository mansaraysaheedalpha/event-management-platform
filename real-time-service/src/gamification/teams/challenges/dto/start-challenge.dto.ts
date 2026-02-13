// src/gamification/teams/challenges/dto/start-challenge.dto.ts
import { IsNotEmpty, IsString } from 'class-validator';

export class StartChallengeDto {
  @IsString()
  @IsNotEmpty()
  challengeId: string;

  @IsString()
  @IsNotEmpty()
  idempotencyKey: string;
}
