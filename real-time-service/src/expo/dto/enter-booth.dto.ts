// src/expo/dto/enter-booth.dto.ts
import { IsUUID } from 'class-validator';

export class EnterBoothDto {
  @IsUUID()
  boothId: string;

  @IsUUID()
  eventId: string;
}
