//src/ops/backchannel/dto/send-backchannel-message.dto.ts
import {
  IsEnum,
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUUID,
  MaxLength,
} from 'class-validator';

// Define the roles that can be targeted
export enum TargetableRole {
  SPEAKER = 'SPEAKER',
  MODERATOR = 'MODERATOR',
  STAFF = 'STAFF',
}

export class SendBackchannelMessageDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(2000)
  text: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;

  // --- ADD THESE NEW OPTIONAL FIELDS ---
  @IsUUID('4')
  @IsOptional()
  targetUserId?: string;

  @IsEnum(TargetableRole)
  @IsOptional()
  targetRole?: TargetableRole;
}
