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
  @IsString()
  @IsNotEmpty()
  @MaxLength(200)
  text: string;
}

export class CreatePollDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(500)
  question: string;

  @IsArray()
  @ValidateNested({ each: true })
  @MinLength(2) // A poll must have at least 2 options
  @Type(() => PollOptionDto)
  options: PollOptionDto[];

  @IsUUID(4)
  idempotencyKey: string;
}
