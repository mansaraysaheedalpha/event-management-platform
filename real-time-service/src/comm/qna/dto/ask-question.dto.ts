import {
  IsBoolean,
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUUID,
  MaxLength,
} from 'class-validator';

// Based on the 'askQuestionPayload' schema in our spec
export class AskQuestionDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(500)
  text: string;

  @IsBoolean()
  @IsOptional()
  isAnonymous?: boolean;

  @IsUUID(4)
  idempotencyKey: string;
}
