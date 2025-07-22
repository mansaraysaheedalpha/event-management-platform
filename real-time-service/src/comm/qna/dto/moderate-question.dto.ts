import { IsIn, IsOptional, IsString, IsUUID, MaxLength } from 'class-validator';

// Based on the 'moderateQuestionPayload' schema in our spec
export class ModerateQuestionDto {
  @IsUUID(4)
  questionId: string;

  @IsString()
  @IsIn(['approved', 'dismissed']) // Enforces the allowed status values
  status: 'approved' | 'dismissed';

  @IsString()
  @IsOptional()
  @MaxLength(200)
  moderatorNote?: string;

  @IsUUID(4)
  idempotencyKey: string;
}
