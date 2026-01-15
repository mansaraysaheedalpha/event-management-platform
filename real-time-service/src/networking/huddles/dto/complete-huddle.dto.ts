//src/networking/huddles/dto/complete-huddle.dto.ts
import { IsNotEmpty, IsString } from 'class-validator';

export class CompleteHuddleDto {
  @IsString()
  @IsNotEmpty()
  huddleId: string;
}
