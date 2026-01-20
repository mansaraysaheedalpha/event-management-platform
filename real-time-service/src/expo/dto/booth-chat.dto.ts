// src/expo/dto/booth-chat.dto.ts
import { IsString, IsOptional, MaxLength, IsInt, Min, Max, IsUUID, IsISO8601 } from 'class-validator';

export class SendBoothChatDto {
  @IsUUID()
  boothId: string;

  @IsString()
  @MaxLength(2000)
  text: string;
}

export class GetBoothChatHistoryDto {
  @IsUUID()
  boothId: string;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(100)
  limit?: number;

  @IsOptional()
  @IsISO8601()
  cursor?: string;
}
