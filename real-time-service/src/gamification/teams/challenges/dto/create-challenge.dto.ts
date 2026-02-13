// src/gamification/teams/challenges/dto/create-challenge.dto.ts
import { IsEnum, IsInt, IsNotEmpty, IsObject, IsOptional, IsString, Max, Min } from 'class-validator';
import { ChallengeType, PointReason } from '@prisma/client';

export class CreateChallengeDto {
  @IsString()
  @IsNotEmpty()
  name: string;

  @IsString()
  @IsOptional()
  description?: string;

  @IsEnum(ChallengeType)
  type: ChallengeType;

  @IsInt()
  @Min(1)
  @Max(60)
  durationMinutes: number;

  @IsEnum(PointReason)
  @IsOptional()
  trackedReason?: PointReason;

  @IsObject()
  @IsOptional()
  actionWeights?: Record<string, number>;

  @IsInt()
  @Min(0)
  @IsOptional()
  rewardFirst?: number;

  @IsInt()
  @Min(0)
  @IsOptional()
  rewardSecond?: number;

  @IsInt()
  @Min(0)
  @IsOptional()
  rewardThird?: number;

  @IsString()
  @IsNotEmpty()
  idempotencyKey: string;
}
