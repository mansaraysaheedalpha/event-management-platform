// src/expo/dto/leave-booth.dto.ts
import { IsUUID } from 'class-validator';

export class LeaveBoothDto {
  @IsUUID()
  boothId: string;
}
