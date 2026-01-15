//src/networking/huddles/dto/join-huddle.dto.ts
import { IsNotEmpty, IsString } from 'class-validator';

export class JoinHuddleDto {
  @IsString()
  @IsNotEmpty()
  huddleId: string;
}
