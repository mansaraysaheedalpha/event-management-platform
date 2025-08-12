//src/gamification/teams/dto/leave-teams.dto.ts
import { IsNotEmpty, IsUUID } from 'class-validator';

export class LeaveTeamDto {
  @IsUUID('4')
  @IsNotEmpty()
  teamId: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
