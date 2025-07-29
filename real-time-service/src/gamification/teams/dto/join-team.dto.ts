import { IsNotEmpty, IsUUID } from 'class-validator';

export class JoinTeamDto {
  @IsUUID('4')
  @IsNotEmpty()
  teamId: string;
}
