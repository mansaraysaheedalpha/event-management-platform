//src/comm/qna/dto/moderate-question.dto.ts
import {
  IsIn,
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUUID,
  MaxLength,
} from 'class-validator';

/**
 * DTO for moderating a submitted question.
 * Typically used by moderators to approve or dismiss a question,
 * with optional notes for context.
 */
export class ModerateQuestionDto {
  @IsNotEmpty()
  @IsUUID('4')
  questionId: string;

  @IsString()
  @IsIn(['approved', 'dismissed'])
  status: 'approved' | 'dismissed';

  @IsString()
  @IsOptional()
  @MaxLength(200)
  moderatorNote?: string;

  @IsNotEmpty()
  @IsUUID('4')
  idempotencyKey: string;
}
