//src/live/streaming/dto/subtitle-chunk.dto.ts
import {
  IsInt,
  IsISO8601,
  IsNotEmpty,
  IsString,
  IsUUID,
} from 'class-validator';

export class SubtitleChunkDto {
  @IsUUID('4')
  sessionId: string;

  @IsString()
  @IsNotEmpty()
  text: string;

  @IsString()
  language: string;

  @IsISO8601()
  timestamp: string;

  @IsInt()
  duration: number; // in milliseconds
}
