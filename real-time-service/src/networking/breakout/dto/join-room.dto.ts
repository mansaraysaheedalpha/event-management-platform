// src/networking/breakout/dto/join-room.dto.ts
import { IsString } from 'class-validator';

export class JoinRoomDto {
  @IsString()
  roomId: string;
}
