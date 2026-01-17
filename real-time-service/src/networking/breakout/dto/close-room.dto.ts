// src/networking/breakout/dto/close-room.dto.ts
import { IsString } from 'class-validator';

export class CloseRoomDto {
  @IsString()
  roomId: string;
}
