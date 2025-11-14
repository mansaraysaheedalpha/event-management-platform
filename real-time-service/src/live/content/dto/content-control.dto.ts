//src/content/dto/content-control.dto.ts
import {
  IsIn,
  IsInt,
  IsOptional,
  IsString,
  IsUUID,
  Min,
} from 'class-validator';

/**
 * DTO for controlling presentation content actions.
 *
 * Usage example:
 *  const dto = new ContentControlDto();
 *  dto.action = 'NEXT_SLIDE';
 *  dto.idempotencyKey = 'uuid-v4-string';
 *  // optionally dto.slideNumber for 'GO_TO_SLIDE' action
 */
const VALID_ACTIONS = [
  'START',
  'END',
  'NEXT_SLIDE',
  'PREV_SLIDE',
  'GO_TO_SLIDE',
];

export class ContentControlDto {
  @IsString()
  @IsIn(VALID_ACTIONS)
  action: 'START' | 'END' | 'NEXT_SLIDE' | 'PREV_SLIDE' | 'GO_TO_SLIDE';

  @IsString()
  sessionId: string;

  @IsInt()
  @Min(0)
  @IsOptional()
  // This is only required if the action is 'GO_TO_SLIDE'
  slideNumber?: number;

  @IsUUID('4')
  idempotencyKey: string;
}
