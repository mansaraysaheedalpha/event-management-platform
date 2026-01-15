//src/networking/huddles/dto/start-huddle.dto.ts
import { IsNotEmpty, IsString } from 'class-validator';

export class StartHuddleDto {
  @IsString()
  @IsNotEmpty()
  huddleId: string;
}
