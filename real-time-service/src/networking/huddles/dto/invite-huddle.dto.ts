//src/networking/huddles/dto/invite-huddle.dto.ts
import { IsArray, IsNotEmpty, IsString, ArrayMinSize, ArrayMaxSize } from 'class-validator';

export class InviteToHuddleDto {
  @IsString()
  @IsNotEmpty()
  huddleId: string;

  @IsArray()
  @IsString({ each: true })
  @ArrayMinSize(1)
  @ArrayMaxSize(10) // Prevent spam invitations
  userIds: string[];
}
