// src/virtual-stage/dto/get-stage-token.dto.ts
import { IsString, IsBoolean, IsOptional } from 'class-validator';

export class GetStageTokenDto {
  @IsString()
  sessionId: string;

  @IsString()
  roomName: string;

  @IsBoolean()
  isSpeaker: boolean;

  @IsOptional()
  @IsBoolean()
  broadcastOnly?: boolean;
}
