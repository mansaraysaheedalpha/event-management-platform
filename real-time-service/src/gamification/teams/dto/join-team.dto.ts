//src/gamification/teams/dto/join-teams.dto.ts
import { IsNotEmpty, IsUUID } from 'class-validator';

export class JoinTeamDto {
  @IsUUID('4')
  @IsNotEmpty()
  teamId: string;

  @IsUUID('4')
  @IsNotEmpty()
  idempotencyKey: string;
}
