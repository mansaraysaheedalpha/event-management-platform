//src/comm/polls/dto/start-giveaway.dto.ts
import { Type } from 'class-transformer';
import {
  IsNotEmpty,
  IsString,
  IsUUID,
  MaxLength,
  IsOptional,
  ValidateNested,
  IsNumber,
  IsIn,
  Min,
} from 'class-validator';

export class PrizeDetailsDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(255)
  title: string;

  @IsString()
  @IsOptional()
  @MaxLength(1000)
  description?: string;

  @IsString()
  @IsOptional()
  @IsIn(['physical', 'virtual', 'voucher'])
  type?: string;

  @IsNumber()
  @IsOptional()
  @Min(0)
  value?: number;

  @IsString()
  @IsOptional()
  @MaxLength(1000)
  claimInstructions?: string;

  @IsString()
  @IsOptional()
  @MaxLength(500)
  claimLocation?: string;

  @IsNumber()
  @IsOptional()
  @Min(1)
  claimDeadlineHours?: number;
}

export class StartGiveawayDto {
  @IsUUID('4')
  @IsNotEmpty()
  pollId: string;

  @IsUUID('4')
  @IsNotEmpty()
  winningOptionId: string;

  @ValidateNested()
  @Type(() => PrizeDetailsDto)
  @IsOptional()
  prize?: PrizeDetailsDto;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
