// src/networking/follow-up/dto/generate-follow-up.dto.ts
import { IsString, IsOptional, IsEnum, MaxLength } from 'class-validator';

export enum FollowUpTone {
  PROFESSIONAL = 'professional',
  FRIENDLY = 'friendly',
  CASUAL = 'casual',
}

export class GenerateFollowUpDto {
  @IsString()
  connectionId: string;

  @IsOptional()
  @IsEnum(FollowUpTone)
  tone?: FollowUpTone = FollowUpTone.PROFESSIONAL;

  @IsOptional()
  @IsString()
  @MaxLength(500)
  additionalContext?: string;
}

export class FollowUpSuggestionResponse {
  connectionId: string;
  suggestedSubject: string;
  suggestedMessage: string;
  talkingPoints: string[];
  contextUsed: string[];
}
