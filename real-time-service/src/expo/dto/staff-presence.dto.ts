// src/expo/dto/staff-presence.dto.ts
import { IsEnum, IsUUID } from 'class-validator';

export enum StaffPresenceStatusDto {
  ONLINE = 'ONLINE',
  AWAY = 'AWAY',
  BUSY = 'BUSY',
  OFFLINE = 'OFFLINE',
}

export class UpdateStaffPresenceDto {
  @IsUUID()
  boothId: string;

  @IsEnum(StaffPresenceStatusDto)
  status: StaffPresenceStatusDto;
}

export class JoinBoothAsStaffDto {
  @IsUUID()
  boothId: string;
}
