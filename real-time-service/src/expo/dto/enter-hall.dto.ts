// src/expo/dto/enter-hall.dto.ts
import { IsUUID } from 'class-validator';

export class EnterHallDto {
  @IsUUID()
  eventId: string;
}
