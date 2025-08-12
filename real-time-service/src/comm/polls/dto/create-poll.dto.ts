//src/comm/polls/dto/create-poll.dto.ts
import {
  IsArray,
  IsNotEmpty,
  IsString,
  IsUUID,
  MaxLength,
  MinLength,
  ValidateNested,
} from 'class-validator';
import { Type } from 'class-transformer';

class PollOptionDto {
  /**
   * Represents a single poll option.
   * Text must be a non-empty string up to 200 characters.
   */
  @IsString()
  @IsNotEmpty()
  @MaxLength(200)
  text: string;
}

/**
 * DTO for creating a new poll with a question and options.
 * Includes an idempotency key to prevent duplicate poll creation.
 */
export class CreatePollDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(500)
  question: string;

  @IsArray()
  @ValidateNested({ each: true })
  @MinLength(2)
  @Type(() => PollOptionDto)
  options: PollOptionDto[];

  @IsNotEmpty()
  @IsUUID('4')
  idempotencyKey: string;
}
