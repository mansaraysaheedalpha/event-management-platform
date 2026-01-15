//src/networking/recommendations/dto/get-recommendations.dto.ts
import {
  IsNotEmpty,
  IsString,
  IsOptional,
  IsNumber,
  IsUUID,
  Min,
  Max,
  IsBoolean,
} from 'class-validator';
import { Transform, Type } from 'class-transformer';

/**
 * DTO for requesting AI-powered recommendations
 */
export class GetRecommendationsDto {
  @Type(() => Number)
  @IsNumber()
  @IsOptional()
  @Min(1)
  @Max(50)
  limit?: number = 10;

  @Transform(({ value }) => value === 'true' || value === true)
  @IsBoolean()
  @IsOptional()
  refresh?: boolean = false;
}

/**
 * Query params for recommendation list
 */
export class RecommendationQueryDto {
  @IsString()
  @IsOptional()
  filterByIndustry?: string;

  @IsString()
  @IsOptional()
  filterByGoal?: string;

  @IsNumber()
  @IsOptional()
  @Min(0)
  @Max(100)
  minMatchScore?: number;
}
