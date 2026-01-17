// src/networking/breakout/dto/leave-room.dto.ts
import { IsString } from 'class-validator';

export class LeaveRoomDto {
  @IsString()
  roomId: string;
}
