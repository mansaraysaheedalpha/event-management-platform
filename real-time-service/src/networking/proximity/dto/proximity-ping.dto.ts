//src/networking/proximity/dto/proximity-ping.dto.ts
import {
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUUID,
  MaxLength,
} from 'class-validator';

export class ProximityPingDto {
  @IsUUID('4')
  @IsNotEmpty()
  targetUserId: string;

  @IsString()
  @MaxLength(255)
  @IsOptional()
  message?: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
