// src/expo/dto/leave-queue.dto.ts
import { IsString } from 'class-validator';

export class LeaveQueueDto {
  @IsString()
  boothId: string;
}
