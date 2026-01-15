//src/networking/huddles/dto/leave-huddle.dto.ts
import { IsNotEmpty, IsString } from 'class-validator';

export class LeaveHuddleDto {
  @IsString()
  @IsNotEmpty()
  huddleId: string;
}
