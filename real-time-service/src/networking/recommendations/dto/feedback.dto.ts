//src/networking/recommendations/dto/feedback.dto.ts
import {
  IsNotEmpty,
  IsString,
  IsOptional,
  IsInt,
  IsBoolean,
  IsArray,
  IsEnum,
  IsIn,
  Min,
  Max,
  MaxLength,
} from 'class-validator';
import { RecommendationAction } from '@prisma/client';

/**
 * DTO for submitting connection feedback
 */
export class SubmitConnectionFeedbackDto {
  @IsString()
  @IsNotEmpty()
  connectionId: string;

  @IsInt({ message: 'Rating must be an integer' })
  @Min(1, { message: 'Rating must be at least 1' })
  @Max(5, { message: 'Rating must be at most 5' })
  rating: number;

  @IsBoolean()
  @IsOptional()
  wasValuable?: boolean;

  @IsBoolean()
  @IsOptional()
  willFollowUp?: boolean;

  @IsBoolean()
  @IsOptional()
  wouldRecommend?: boolean;

  @IsArray()
  @IsString({ each: true })
  @IsOptional()
  positiveFactors?: string[];

  @IsArray()
  @IsString({ each: true })
  @IsOptional()
  negativeFactors?: string[];

  @IsString()
  @IsOptional()
  @MaxLength(1000)
  comments?: string;
}

/**
 * DTO for submitting recommendation feedback
 */
export class SubmitRecommendationFeedbackDto {
  @IsString()
  @IsNotEmpty()
  recommendationId: string;

  @IsEnum(RecommendationAction)
  action: RecommendationAction;

  @IsInt({ message: 'Connection rating must be an integer' })
  @IsOptional()
  @Min(1, { message: 'Connection rating must be at least 1' })
  @Max(5, { message: 'Connection rating must be at most 5' })
  connectionRating?: number;

  @IsString()
  @IsOptional()
  @MaxLength(255)
  skipReason?: string;
}

/**
 * Positive factors for connection feedback
 */
export const POSITIVE_FACTORS = [
  'shared_interests',
  'goal_alignment',
  'good_conversation',
  'valuable_insights',
  'potential_collaboration',
  'career_opportunity',
] as const;

/**
 * Negative factors for connection feedback
 */
export const NEGATIVE_FACTORS = [
  'not_relevant',
  'wrong_industry',
  'awkward_interaction',
  'no_common_ground',
  'already_knew',
  'too_busy',
] as const;

/**
 * Skip reasons for recommendation feedback
 */
export const SKIP_REASONS = [
  'not_relevant',
  'already_know',
  'too_busy',
  'not_interested',
  'wrong_timing',
] as const;
