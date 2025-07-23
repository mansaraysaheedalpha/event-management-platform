import {
  IsBoolean,
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUUID,
  MaxLength,
} from 'class-validator';

/**
 * DTO for asking a new question during a session or event.
 * Supports anonymous questions and enforces character limits.
 */
export class AskQuestionDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(500)
  text: string;

  @IsBoolean()
  @IsOptional()
  isAnonymous?: boolean;

  @IsUUID('4')
  idempotencyKey: string;
}
