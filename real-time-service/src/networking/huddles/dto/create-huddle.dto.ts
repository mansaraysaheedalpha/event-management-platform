//src/networking/huddles/dto/create-huddle.dto.ts
import {
  IsString,
  IsNotEmpty,
  IsOptional,
  IsInt,
  Min,
  Max,
  IsDateString,
  IsEnum,
  MaxLength,
  IsUUID,
} from 'class-validator';
import { HuddleType } from '@prisma/client';

export class CreateHuddleDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(100)
  topic: string;

  @IsString()
  @IsOptional()
  @MaxLength(1000)
  problemStatement?: string;

  @IsString()
  @IsOptional()
  @MaxLength(500)
  description?: string;

  @IsString()
  @IsNotEmpty()
  eventId: string;

  @IsString()
  @IsOptional()
  sessionId?: string;

  @IsString()
  @IsOptional()
  @MaxLength(255)
  locationName?: string;

  @IsString()
  @IsOptional()
  @MaxLength(500)
  locationDetails?: string;

  @IsDateString()
  @IsNotEmpty()
  scheduledAt: string;

  @IsInt()
  @Min(5)
  @Max(60)
  @IsOptional()
  duration?: number;

  @IsEnum(HuddleType)
  @IsOptional()
  huddleType?: HuddleType;

  @IsInt()
  @Min(2)
  @Max(4)
  @IsOptional()
  minParticipants?: number;

  @IsInt()
  @Min(2)
  @Max(10)
  @IsOptional()
  maxParticipants?: number;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
