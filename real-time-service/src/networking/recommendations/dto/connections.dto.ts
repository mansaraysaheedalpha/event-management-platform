//src/networking/recommendations/dto/connections.dto.ts

import { IsInt, IsOptional, Min, Max } from 'class-validator';
import { Type } from 'class-transformer';

/**
 * Query parameters for getting connections
 */
export class GetConnectionsDto {
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  limit?: number = 50;
}

/**
 * User info for a connection (person you connected with)
 * NOTE: Excludes sensitive fields like email/phone for security
 */
export interface ConnectedUserInfo {
  id: string;
  name: string;
  role?: string;
  company?: string;
  avatarUrl?: string;
  linkedInUrl?: string;
  githubUsername?: string;
  twitterHandle?: string;
}

/**
 * Single connection response - represents a user you've connected with
 */
export interface ConnectionDto {
  id: string; // recommendation ID
  connectedUserId: string;
  connectedAt: Date;
  matchScore: number;
  reasons: string[];
  user: ConnectedUserInfo;
}

/**
 * Response for user's connections list
 */
export interface ConnectionsResponseDto {
  connections: ConnectionDto[];
  total: number;
}
