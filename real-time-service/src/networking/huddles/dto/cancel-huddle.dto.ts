//src/networking/huddles/dto/cancel-huddle.dto.ts
import { IsNotEmpty, IsOptional, IsString, MaxLength } from 'class-validator';

export class CancelHuddleDto {
  @IsString()
  @IsNotEmpty()
  huddleId: string;

  @IsString()
  @IsOptional()
  @MaxLength(500)
  reason?: string;
}
