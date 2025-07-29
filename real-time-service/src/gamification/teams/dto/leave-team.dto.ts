import { IsNotEmpty, IsUUID } from 'class-validator';

export class LeaveTeamDto {
  @IsUUID('4')
  @IsNotEmpty()
  teamId: string;
}
