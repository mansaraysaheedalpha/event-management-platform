//src/networking/recommendations/dto/track-recommendation.dto.ts
import { IsNotEmpty, IsString, IsOptional, IsUUID } from 'class-validator';

/**
 * DTO for tracking recommendation views
 */
export class TrackViewedDto {
  @IsUUID()
  @IsNotEmpty()
  recommendationId: string;
}

/**
 * DTO for tracking recommendation pings
 */
export class TrackPingedDto {
  @IsUUID()
  @IsNotEmpty()
  recommendationId: string;

  @IsString()
  @IsOptional()
  message?: string;
}

/**
 * DTO for tracking when recommendation led to connection
 */
export class TrackConnectedDto {
  @IsUUID()
  @IsNotEmpty()
  recommendationId: string;
}
