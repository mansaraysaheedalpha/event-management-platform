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
  'STOP',
  'END',
  'NEXT_SLIDE',
  'PREV_SLIDE',
  'GO_TO_SLIDE',
];

export class ContentControlDto {
  @IsString()
  @IsIn(VALID_ACTIONS)
  action: 'START' | 'STOP' | 'END' | 'NEXT_SLIDE' | 'PREV_SLIDE' | 'GO_TO_SLIDE';

  @IsString()
  sessionId: string;

  @IsInt()
  @Min(1)
  @IsOptional()
  // This is only required if the action is 'GO_TO_SLIDE'
  slideNumber?: number;

  @IsInt()
  @Min(1)
  @IsOptional()
  // Alternative name for slideNumber (frontend compatibility)
  targetSlide?: number;

  @IsUUID('4')
  idempotencyKey: string;
}
