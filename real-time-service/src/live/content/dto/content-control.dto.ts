import {
  IsIn,
  IsInt,
  IsOptional,
  IsString,
  IsUUID,
  Min,
} from 'class-validator';

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

  @IsInt()
  @Min(0)
  @IsOptional()
  // This is only required if the action is 'GO_TO_SLIDE'
  slideNumber?: number;

  @IsUUID(4)
  idempotencyKey: string;
}
