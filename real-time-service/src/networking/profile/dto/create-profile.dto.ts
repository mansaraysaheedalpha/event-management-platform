//src/networking/profile/dto/create-profile.dto.ts
import {
  IsString,
  IsOptional,
  IsArray,
  IsEnum,
  IsUrl,
  MaxLength,
  ArrayMaxSize,
} from 'class-validator';

/**
 * Networking goals that users can select during registration
 */
export enum NetworkingGoal {
  LEARN = 'LEARN',
  NETWORK = 'NETWORK',
  HIRE = 'HIRE',
  GET_HIRED = 'GET_HIRED',
  FIND_PARTNERS = 'FIND_PARTNERS',
  FIND_INVESTORS = 'FIND_INVESTORS',
  SELL = 'SELL',
  BUY = 'BUY',
  MENTOR = 'MENTOR',
  GET_MENTORED = 'GET_MENTORED',
}

/**
 * DTO for creating/updating user networking profile
 *
 * Used during event registration to collect data for AI recommendations.
 * All fields are optional to support progressive profile completion.
 */
export class CreateProfileDto {
  @IsArray()
  @IsEnum(NetworkingGoal, { each: true })
  @ArrayMaxSize(5, { message: 'You can select up to 5 goals' })
  @IsOptional()
  goals?: NetworkingGoal[];

  @IsArray()
  @IsString({ each: true })
  @ArrayMaxSize(10, { message: 'You can select up to 10 interests' })
  @IsOptional()
  interests?: string[];

  @IsString()
  @MaxLength(500)
  @IsOptional()
  bio?: string;

  @IsString()
  @IsOptional()
  industry?: string;

  @IsArray()
  @IsString({ each: true })
  @ArrayMaxSize(10)
  @IsOptional()
  skillsToOffer?: string[];

  @IsArray()
  @IsString({ each: true })
  @ArrayMaxSize(10)
  @IsOptional()
  skillsNeeded?: string[];

  // Social media links - all optional
  @IsUrl({}, { message: 'Please enter a valid LinkedIn URL' })
  @IsOptional()
  linkedInUrl?: string;

  @IsString()
  @IsOptional()
  githubUsername?: string;

  @IsString()
  @IsOptional()
  twitterHandle?: string;

  @IsUrl({}, { message: 'Please enter a valid Facebook URL' })
  @IsOptional()
  facebookProfileUrl?: string;

  @IsString()
  @IsOptional()
  instagramHandle?: string;

  @IsUrl({}, { message: 'Please enter a valid YouTube URL' })
  @IsOptional()
  youtubeChannelUrl?: string;

  @IsUrl({}, { message: 'Please enter a valid website URL' })
  @IsOptional()
  personalWebsite?: string;

  /**
   * Free-text field for users without social media presence
   * They can describe what they're looking for at the event
   */
  @IsString()
  @MaxLength(1000)
  @IsOptional()
  eventExpectations?: string;
}

/**
 * Response DTO for profile operations
 */
export class ProfileResponseDto {
  id: string;
  userId: string;
  goals: string[];
  interests: string[];
  bio?: string;
  industry?: string;
  skillsToOffer: string[];
  skillsNeeded: string[];
  linkedInUrl?: string;
  githubUsername?: string;
  twitterHandle?: string;
  profileCompleteness: number;
  createdAt: Date;
  updatedAt: Date;
}
