//src/networking/recommendations/dto/recommendation-response.dto.ts

/**
 * User display info for recommendation cards
 * NOTE: Excludes sensitive fields like email/phone for security
 */
export interface RecommendedUserInfo {
  id: string;
  name: string;
  role?: string;
  company?: string;
  avatarUrl?: string;
  linkedInUrl?: string;
  githubUsername?: string;
  twitterHandle?: string;
  industry?: string;
  goals?: string[];
}

/**
 * Single recommendation response
 */
export interface RecommendationDto {
  id: string;
  userId: string;
  recommendedUserId: string;
  matchScore: number;
  reasons: string[];
  conversationStarters: string[];
  potentialValue?: string;
  generatedAt: Date;
  expiresAt: Date;
  viewed: boolean;
  pinged: boolean;
  connected: boolean;
  user: RecommendedUserInfo;
}

/**
 * Paginated recommendations response
 */
export interface RecommendationsResponseDto {
  recommendations: RecommendationDto[];
  total: number;
  hasMore: boolean;
  generatedAt?: Date;
  expiresAt?: Date;
}
