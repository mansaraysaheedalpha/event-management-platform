//src/networking/huddles/dto/respond-huddle.dto.ts
import { IsEnum, IsNotEmpty, IsString } from 'class-validator';

export enum HuddleResponseType {
  ACCEPT = 'accept',
  DECLINE = 'decline',
}

export class RespondHuddleDto {
  @IsString()
  @IsNotEmpty()
  huddleId: string;

  @IsEnum(HuddleResponseType)
  @IsNotEmpty()
  response: HuddleResponseType;
}
